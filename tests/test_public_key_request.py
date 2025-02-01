# """The middleman between Plover and the server."""

import os
from plover.oslayer.config import CONFIG_DIR

from plover_websocket_server.config import ServerConfig
from plover_websocket_server.websocket.server import WebSocketServer
from asyncio import get_event_loop
from nacl_middleware import Nacl

from json import dump
from os import makedirs

SERVER_CONFIG_FILE = "plover_websocket_server_config.json"
config_path: str = os.path.join(CONFIG_DIR, SERVER_CONFIG_FILE)

def is_ci_environment():
    ci_vars = ['CI', 'TRAVIS', 'GITHUB_ACTIONS', 'CIRCLECI', 'JENKINS_HOME']
    return any(var in os.environ for var in ci_vars)

if is_ci_environment():
    # Make sure there is a config folder
    makedirs(CONFIG_DIR, exist_ok=True)

    # random data
    data = {
    "private_key": "f4a8ac4dcee327231712ded32f6171962b8a430efa20a1c8c2943c6fdf05074e",
    "public_key": "a76e938fb83d0d95b8b1f249f9aa1ab47c5159f31a052e1d366d18488573ee30",
    "host": "localhost",
    "port": 8086,
    "remotes": [
        {
        "pattern": "^https?\\:\\/\\/localhost?(:[0-9]*)?"
        }
    ]
    }

    with open(config_path, "w", encoding="utf-8") as config_file:
        dump(data, config_file, indent=2)


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