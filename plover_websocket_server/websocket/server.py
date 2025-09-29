"""WebSocket server definition."""

from asyncio import CancelledError, Event, create_task, new_event_loop, set_event_loop
from json import decoder
from operator import itemgetter
from os.path import join
from ssl import Purpose, SSLContext, create_default_context
from typing import TypedDict

from aiohttp import WSCloseCode, WSMsgType
from aiohttp.web import (
    Application,
    AppRunner,
    Request,
    Response,
    TCPSite,
    WebSocketResponse,
    json_response,
)
from aiohttp_middlewares import cors_middleware
from aiohttp_middlewares.cors import DEFAULT_ALLOW_HEADERS, DEFAULT_ALLOW_METHODS
from nacl.public import PrivateKey
from nacl_middleware import MailBox, Nacl, nacl_middleware
from plover import log
from plover.oslayer.config import CONFIG_DIR

from plover_websocket_server.errors import ERROR_NO_SERVER, ERROR_SERVER_RUNNING
from plover_websocket_server.server import EngineServer, ServerStatus
from plover_websocket_server.websocket.app_keys import app_keys
from plover_websocket_server.websocket.views import index


class SSLConfig(TypedDict):
    cert_path: str
    key_path: str


class WebSocketServer(EngineServer):
    """A server based on WebSockets."""

    _app: Application
    _ssl: SSLConfig
    _remotes: list[object]
    _private_key: PrivateKey
    _runner: AppRunner
    _site: TCPSite
    _ssl_context: SSLContext

    def __init__(
        self,
        host: str,
        port: str,
        ssl: SSLConfig,
        remotes: list[object],
        private_key: PrivateKey,
    ) -> None:
        """Initialize the server.

        Args:
            host: The host address for the server to run on.
            port: The port for the server to run on.
        """

        super().__init__(host, port)
        self._app = None
        self._private_key = private_key
        self._remotes = remotes
        if ssl:
            cert_path: str = join(CONFIG_DIR, ssl["cert_path"])
            key_path: str = join(CONFIG_DIR, ssl["key_path"])
            self._ssl_context = create_default_context(
                Purpose.CLIENT_AUTH, cafile=cert_path
            )
            self._ssl_context.load_cert_chain(cert_path, key_path)
        else:
            self._ssl_context = None

    async def get_public_key(self, request: Request) -> Response:
        """Route to get the public key of the web server.

        Args:
            request: The request from the client.
        """
        log.info("Request to get the server public key received.")
        log.info("Decoding public key...")
        decoded_public_key = Nacl(self._private_key).decoded_public_key()
        log.info(f"Public key {decoded_public_key} was decoded!")
        return json_response(decoded_public_key)

    async def protocol(self, request: Request) -> Response:
        """Route to get the protocol of the web server.

        Args:
            request: The request from the client.
        """
        if self._ssl_context:
            protocol = "wss://"
        else:
            protocol = "ws://"

        mail_box: MailBox = itemgetter("mail_box")(request)

        return json_response(mail_box.box(protocol))

    async def websocket_handler(self, request: Request) -> WebSocketResponse:
        """The main WebSocket handler.

        Args:
            request: The request from the client.
        """
        log.info("WebSocket connection starting")
        socket = WebSocketResponse()
        await socket.prepare(request)
        sockets: list[WebSocketResponse] = request.app[app_keys["websockets"]]
        mail_box: MailBox = itemgetter("mail_box")(request)
        socket["mail_box"] = mail_box
        sockets.append(socket)
        log.info("WebSocket connection ready")

        try:
            async for message in socket:
                if message.type == WSMsgType.TEXT:
                    # Handle unencrypted heartbeat first
                    if message.data == "ping":
                        await socket.send_str("pong")
                        continue

                    try:
                        log.debug("Decrypting message...")
                        decrypted: dict = mail_box.unbox(message.data)
                        log.debug(f"Received encrypted message {decrypted}")
                    except Exception:
                        log.info(f"Failed decrypting data: {message.data}")
                        continue

                    if decrypted == "close":
                        await socket.close()
                        continue

                    self.data.status = {"decrypted": decrypted, "socket": socket}

                elif message.type == WSMsgType.ERROR:
                    log.info(
                        "WebSocket connection closed with exception "
                        f"{socket.exception()}"
                    )
        except CancelledError:  # https://github.com/aio-libs/aiohttp/issues/1768
            pass
        finally:
            await socket.close()

        sockets.remove(socket)
        log.info("WebSocket connection closed")
        return socket

    def _start(self) -> None:
        """Starts the server.

        Will create a blocking event loop.
        """
        if self.listened.status == ServerStatus.Running:
            raise AssertionError(ERROR_SERVER_RUNNING)

        loop = new_event_loop()
        set_event_loop(loop)
        self._loop = loop

        self._app = Application(
            middlewares=[
                cors_middleware(
                    origins=self._remotes,
                    allow_methods=DEFAULT_ALLOW_METHODS,
                    allow_headers=(
                        *DEFAULT_ALLOW_HEADERS,
                        "ngrok-skip-browser-warning",
                    ),
                ),
                nacl_middleware(
                    self._private_key, exclude_routes=("/getpublickey",), log=log
                ),
            ]
        )

        async def on_shutdown(app) -> None:
            sockets: list[WebSocketResponse] = app[app_keys["websockets"]]
            for ws in set(sockets):
                await ws.close()

        self._app.on_shutdown.append(on_shutdown)

        self._app[app_keys["websockets"]] = []

        self._app.router.add_get("/", index)
        self._app.router.add_get("/protocol", self.protocol)
        self._app.router.add_get("/websocket", self.websocket_handler)
        self._app.router.add_get("/getpublickey", self.get_public_key)

        self._app.on_shutdown.append(self._on_server_shutdown)

        self._stop_event = Event()

        async def run_async() -> None:
            self._runner = runner = AppRunner(self._app)
            await runner.setup()
            self._site = site = TCPSite(
                runner, host=self._host, port=self._port, ssl_context=self._ssl_context
            )
            await site.start()
            self.listened.status = ServerStatus.Running
            await self._stop_event.wait()
            await runner.cleanup()
            self._app = None
            self._loop = None
            self.listened.status = ServerStatus.Stopped

        loop.run_until_complete(run_async())

    async def _stop(self) -> None:
        """Stops the server.

        Performs any clean up operations as needed.
        """

        if self.listened.status != ServerStatus.Running:
            raise AssertionError(ERROR_NO_SERVER)

        self._stop_event.set()

    async def _on_server_shutdown(self, app: Application) -> None:
        """Handles pre-shutdown behavior for the server.

        Args:
            app: The web application shutting down.
        """

        sockets: list[WebSocketResponse] = app.get(app_keys["websockets"], [])
        for socket in sockets:
            await socket.close(code=WSCloseCode.GOING_AWAY, message="Server shutdown")

    async def _broadcast_message(self, data: dict) -> None:
        """Broadcasts a message to connected clients.

        Args:
            data: The data to broadcast. Internally it's sent with WebSocketResponse.send_str.
        """

        if not self._app:
            return

        sockets: list[WebSocketResponse] = self._app.get(app_keys["websockets"], [])

        async def task(socket: WebSocketResponse):
            try:
                log.debug("Retrieving mail box...")
                mail_box: MailBox = itemgetter("mail_box")(socket)
                log.debug(f"Mail box {mail_box} retrieved!")
                log.debug("Encrypting data...")
                encrypted_data = mail_box.box(data)
                log.debug(f"Data {encrypted_data} encrypted!")
                await socket.send_str(encrypted_data)
            except Exception as e:
                print(
                    f"Failed to update websocket {socket} {id(socket)} {socket.closed}: {e}",
                    flush=True,
                )

        # Create background tasks for each socket
        for socket in sockets:
            create_task(task(socket))

        # Filter out closed sockets
        sockets[:] = [socket for socket in sockets if not socket.closed]
