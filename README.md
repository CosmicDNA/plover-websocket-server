# Plover WebSocket Server

[![Python Tests](https://github.com/CosmicDNA/plover-websocket-server/actions/workflows/pytest.yml/badge.svg)](https://github.com/CosmicDNA/plover-websocket-server/actions/workflows/pytest.yml)
[![PyPI](https://img.shields.io/pypi/v/plover-websocket-server?style=flat)](https://pypi.python.org/pypi/plover-websocket-server/)

A WebSocket server for exposing [Plover](https://github.com/openstenoproject/plover) events
and controlling Plover from an external program.

This plugin is available on [GitHub](https://github.com/CosmicDNA/plover-websocket-server)
and [PyPI](https://pypi.org/project/plover-websocket-server/) (under the name `plover-websocket-server`).
Report all bugs on GitHub.

## Installation

Download the latest version of Plover for your operating system from the [releases page](https://github.com/openstenoproject/plover/releases). Only versions 4.0.0.dev8 and higher are supported.

1. Open Plover
2. Navigate to the Plugin Manager tool
3. Select the "plover-websocket-server" plugin entry in the list
4. Click install
5. Restart Plover

The same method can be used for updating and uninstalling the plugin.

## Configuration

A file named `plover_websocket_server_config.json` will be created
inside Plover's configuration directory (same directory as `plover.cfg` file).

Example content:

```json
{
    "private_key": "eb700b05b84a14b81ea69d5f826fc4ca30310db22f8943b1975fe56043c00771",
    "public_key": "3a283210963d849642011731ba048e8d8f2272802902a9ef7de56d0116236801",
    "host": "localhost",
    "port": 8086,
    "remotes": [
        {
            "pattern": "^https?\\:\\/\\/localhost?(:[0-9]*)?"
        }
    ],
    "ssl": {
        "cert_path": "/path/to/cert.pem",
        "key_path": "/path/to/key.pem"
    }
}
```

All fields are optional. But if you specify either a private or public key you need the opposed matching key also specified. The same pattern applies to the pair of ssl paths.

The default is included in the example above except for the private and public keys and the ssl paths which are just an example.

In the remotes config, either an object with a Regex pattern, or a string are supported. This is important to allow [Cross Origin Resource Sharing (CORS)](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) for the specific case where your client runs on a browser.

> [!NOTE]
> This plugin utilises assymetric key encryption to protect the plugin from unauthorised access and is powered by [Pynacl](https://github.com/pyca/pynacl/).

## How to Use

* Enable it in Configure -> Plugins
* Connect to ws://localhost:8086/websocket with your client and get the data pushed to you as
event: data formatted JSON.

Received data format: Search for occurrences of `queue_message` in `plover_websocket_server/manager.py`,
or write an example program
and observe its output.

> [!TIP]
> Use the existing example script `test/client_example.py` to interact with the plugin.

Controlling Plover from other programs:

* Sending 'close' disconnects you.
* Sending a valid JSON string will execute the specified action.
For example `{"stroke": ["S-"]}` (note that invalid keys are silently dropped),
or `{"translation": "abc"}`.

If there's some error during the execution, it will be silently ignored and printed on stderr.

If the `"force"` key is `true` then the command will be executed even when the engine is turned off.
Note that `{PLOVER:RESUME}` will have no effect in that case.

Because the Plover inner working is closely tied to the assumption
that strokes can only come from the keyboard, when `{PLOVER:RESUME}` (or a command with similar effect,
such as `{PLOVER:TOGGLE}`) is sent and the machine is
"Keyboard" then some characters before the cursor will be deleted.
To prevent this, set the `"zero_last_stroke_length"` key to `true`.

> [!WARNING]
> This should be used very sparingly because it may have unintended effects.

## Acknowlegements

Forked from https://github.com/user202729/plover_websocket_server.
