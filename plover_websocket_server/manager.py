"""The middleman between Plover and the server."""

import os
from datetime import datetime
from json import loads
from operator import itemgetter
from typing import List

from aiohttp.web import WebSocketResponse
from jsonpickle import encode
from plover import log
from plover.config import Config
from plover.engine import StenoEngine
from plover.formatting import _Action
from plover.gui_qt.paper_tape import TapeModel
from plover.oslayer.config import CONFIG_DIR
from plover.steno import Stroke
from plover.steno_dictionary import StenoDictionaryCollection

from plover_websocket_server.config import ServerConfig
from plover_websocket_server.errors import (
    ERROR_MISSING_ENGINE,
    ERROR_NO_SERVER,
    ERROR_SERVER_RUNNING,
)
from plover_websocket_server.server import EngineServer, ServerStatus
from plover_websocket_server.websocket.server import WebSocketServer

SERVER_CONFIG_FILE = "plover_websocket_server_config.json"


class EngineServerManager:
    """Manages a server that exposes the Plover engine."""

    _server: EngineServer
    _tape_model: TapeModel

    def __init__(self, engine: StenoEngine, test_mode: bool = False) -> None:
        self._server = None
        self._engine: StenoEngine = engine
        self._config_path: str = os.path.join(CONFIG_DIR, SERVER_CONFIG_FILE)
        if self.get_server_status() != ServerStatus.Stopped:
            raise AssertionError(ERROR_SERVER_RUNNING)

        self._config = ServerConfig(
            self._config_path
        )  # reload the configuration when the server is restarted

        self._server = WebSocketServer(
            self._config.host,
            self._config.port,
            self._config.ssl,
            self._config.remotes,
            self._config.private_key,
        )
        self._server.register_message_callback(self._on_message)
        self._test_mode = test_mode
        if not test_mode:
            self._tape_model = TapeModel()
            self._tape_model.reset()

    def start(self) -> None:
        """Starts the server.

        Raises:
            AssertionError: The server failed to start.
            IOError: The server failed to start.
        """
        self._server.start()

        # TODO: Wait until the server actually starts before connecting hooks
        if not self._test_mode:
            self._connect_hooks()

    def raw_stop(self) -> None:
        """Stops the server.

        Raises:
            AssertionError: The server failed to stop.
        """

        if self.get_server_status() != ServerStatus.Running:
            raise AssertionError(ERROR_NO_SERVER)

        if not self._test_mode:
            self._disconnect_hooks()
        else:
            self._server.data.stop_listening()
            self.stop_listening()

        self._server.queue_stop()

    def stop(self) -> None:
        """Stops the server.

        Raises:
            AssertionError: The server failed to stop.
        """

        self.raw_stop()
        log.info("Joining server thread...")
        self._server.join()
        log.info("Server thread joined.")
        self._server = None

    def add_listener(self, listener: callable) -> None:
        self._server.listened.add_listener(listener)

    def stop_listening(self) -> None:
        self._server.listened.stop_listening()

    def get_server_status(self) -> ServerStatus:
        """Gets the status of the server.

        Returns:
            The status of the server.
        """

        return self._server.listened.status if self._server else ServerStatus.Stopped

    def join(self) -> None:
        self._server.join()

    async def _on_message(self, data: dict) -> None:
        decrypted: dict = itemgetter("decrypted")(data)
        if self._test_mode:
            log.info(f"{datetime.now()} Received data {decrypted}")
            socket: WebSocketResponse = itemgetter("socket")(data)
            await socket.send_json(decrypted)
            return
        with self._engine:
            forced_on = False
            if decrypted.get("forced") and not self._engine._is_running:
                forced_on = True
                self._engine._is_running = True

            if decrypted.get("zero_last_stroke_length"):
                self._engine._machine._last_stroke_key_down_count = 0
                self._engine._machine._stroke_key_down_count = 0

            import traceback

            if "stroke" in decrypted:
                steno_keys = decrypted["stroke"]
                if isinstance(steno_keys, list):
                    try:
                        self._engine._machine_stroke_callback(steno_keys)
                    except Exception:
                        traceback.print_exc()

            if "translation" in decrypted:
                mapping = decrypted["translation"]
                if isinstance(mapping, str):
                    try:
                        from plover.steno import Stroke
                        from plover.translation import Translation, _mapping_to_macro

                        stroke = Stroke(
                            []
                        )  # required, because otherwise Plover will try to merge the outlines together
                        # and the outline [] (instead of [Stroke([])]) can be merged to anything
                        macro = _mapping_to_macro(mapping, stroke)
                        if macro is not None:
                            self._engine._translator.translate_macro(macro)
                            return
                        t = (
                            # self._engine._translator._find_translation_helper(stroke) or
                            # self._engine._translator._find_translation_helper(stroke, system.SUFFIX_KEYS) or
                            Translation([stroke], mapping)
                        )
                        self._engine._translator.translate_translation(t)
                        self._engine._translator.flush()
                        # self._engine._trigger_hook('stroked', stroke)
                    except Exception:
                        traceback.print_exc()

            if forced_on:
                self._engine._is_running = False

    def _connect_hooks(self):
        """Creates hooks into all of Plover's events."""

        if not self._engine:
            raise AssertionError(ERROR_MISSING_ENGINE)

        for hook in self._engine.HOOKS:
            try:
                callback = getattr(self, f"_on_{hook}")
            except AttributeError:
                continue
            self._engine.hook_connect(hook, callback)

    def _disconnect_hooks(self):
        """Removes hooks from all of Plover's events."""

        self._server.data.stop_listening()
        if not self._engine:
            raise AssertionError(ERROR_MISSING_ENGINE)

        for hook in self._engine.HOOKS:
            try:
                callback = getattr(self, f"_on_{hook}")
            except AttributeError:
                continue
            self._engine.hook_disconnect(hook, callback)

    def _on_stroked(self, stroke: Stroke):
        """Broadcasts when a new stroke is performed.

        Args:
            stroke: The stroke that was just performed.
        """
        stroke_json = encode(stroke, unpicklable=False)
        paper = self._tape_model._paper_format(stroke)

        data = {
            "keys": stroke.steno_keys,
            "stroked": stroke_json,
            "rtfcre": stroke.rtfcre,
            "paper": paper,
        }
        self._server.queue_message(data)

    def _on_translated(self, old: List[_Action], new: List[_Action]):
        """Broadcasts when a new translation occurs.

        Args:
            old: A list of the previous actions for the current translation.
            new: A list of the new actions for the current translation.
        """

        old_json = encode(old, unpicklable=False)
        new_json = encode(new, unpicklable=False)

        data = {"translated": {"old": loads(old_json), "new": loads(new_json)}}
        self._server.queue_message(data)

    def _on_machine_state_changed(self, machine_type: str, machine_state: str):
        """Broadcasts when the active machine state changes.

        Args:
            machine_type: The name of the active machine.
            machine_state: The new machine state. This should be one of the
                state constants listed in plover.machine.base.
        """

        data = {
            "machine_state_changed": {
                "machine_type": machine_type,
                "machine_state": machine_state,
            }
        }
        self._server.queue_message(data)

    def _on_output_changed(self, enabled: bool):
        """Broadcasts when the state of output changes.

        Args:
            enabled: If the output is now enabled or not.
        """

        data = {"output_changed": enabled}
        self._server.queue_message(data)

    def _on_config_changed(self, config_update: Config):
        """Broadcasts when the configuration changes.

        Args:
            config_update: An object containing the full configuration or a
                part of the configuration that was updated.
        """

        config_json = encode(config_update, unpicklable=False)

        data = {"config_changed": loads(config_json)}
        self._server.queue_message(data)

    def _on_dictionaries_loaded(self, dictionaries: StenoDictionaryCollection):
        """Broadcasts when all of the dictionaries get loaded.

        Args:
            dictionaries: A collection of the dictionaries that loaded.
        """

        data = {"dictionaries_loaded": "0"}
        self._server.queue_message(data)

    def _on_send_string(self, text: str):
        """Broadcasts when a new string is output.

        Args:
            text: The string that was output.
        """

        data = {"send_string": text}
        self._server.queue_message(data)

    def _on_send_backspaces(self, count: int):
        """Broadcasts when backspaces are output.

        Args:
            count: The number of backspaces that were output.
        """

        data = {"send_backspaces": count}
        self._server.queue_message(data)

    def _on_send_key_combination(self, combination: str):
        """Broadcasts when a key combination is output.

        Args:
            combination: A string representing a sequence of key combinations.
                Keys are represented by their names based on the OS-specific
                keyboard implementations in plover.oslayer.
        """

        data = {"send_key_combination": combination}
        self._server.queue_message(data)

    def _on_add_translation(self):
        """Broadcasts when the add translation tool is opened via a command."""

        data = {"add_translation": True}
        self._server.queue_message(data)

    def _on_focus(self):
        """Broadcasts when the main window is focused via a command."""

        data = {"focus": True}
        self._server.queue_message(data)

    def _on_configure(self):
        """Broadcasts when the configuration tool is opened via a command."""

        data = {"configure": True}
        self._server.queue_message(data)

    def _on_lookup(self):
        """Broadcasts when the lookup tool is opened via a command."""

        data = {"lookup": True}
        self._server.queue_message(data)

    def _on_suggestions(self):
        """Broadcasts when the suggestions tool is opened via a command."""

        data = {"suggestions": True}
        self._server.queue_message(data)

    def _on_quit(self):
        """Broadcasts when the application is terminated.

        Can be either a full quit or a restart.
        """

        data = {"quit": True}
        self._server.queue_message(data)
