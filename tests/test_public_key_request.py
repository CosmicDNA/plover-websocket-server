# """The middleman between Plover and the server."""

import os
from plover.oslayer.config import CONFIG_DIR

from plover_websocket_server.config import ServerConfig
from plover_websocket_server.websocket.server import WebSocketServer
from asyncio import get_event_loop
from nacl_middleware import Nacl

SERVER_CONFIG_FILE = "plover_websocket_server_config.json"

config_path: str = os.path.join(CONFIG_DIR, SERVER_CONFIG_FILE)

config = ServerConfig(
    config_path
)  # reload the configuration when the server is restarted

server = WebSocketServer(
    config.host,
    config.port,
    config.ssl,
    config.remotes,
    config.private_key,
)

def test_public_key_request() -> None:
    async def async_test_public_key_request() -> None:
        puk_response = await server.get_public_key(None)
        puk = puk_response.text.strip('\"')
        derived_puk = Nacl(config.private_key).decoded_public_key()
        assert puk == derived_puk

    loop = get_event_loop()
    loop.run_until_complete(async_test_public_key_request())