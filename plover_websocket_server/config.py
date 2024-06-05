"""Server configuration."""

from copy import deepcopy
from json import dump, load
from re import compile

from nacl.encoding import HexEncoder
from nacl.public import PrivateKey
from nacl_middleware import Nacl
from plover import log

DEFAULT_HOST: str = "localhost"
DEFAULT_PORT: int = 8086


class ServerConfig:
    """Loads server configuration.

    Attributes:
        host: The host address for the server to run on.
        port: The port for the server to run on.
    """

    host: str
    port: str

    def __init__(self, file_path: str) -> None:
        """Initialize the server configuration object.

        Args:
            file_path: The file path of the configuration file to load.

        Raises:
            IOError: Errored when loading the server configuration file.
        """

        try:
            with open(file_path, encoding="utf-8") as config_file:
                data: dict = load(config_file)
        except FileNotFoundError:
            data = {}
        loaded_data = deepcopy(data)

        encoder = HexEncoder
        # Generate a new private key if not already present
        if "private_key" not in data or "public_key" not in data:
            log.debug("Instancing Nacl...")
            nacl_helper = Nacl()
            log.debug(f"Nacl {nacl_helper} instanced!")
            private_key = nacl_helper.private_key
            log.debug("Decoding private key...")
            decoded_private_key = nacl_helper.decoded_private_key()
            log.debug(f"Private key {decoded_private_key} decoded!")
            data["private_key"] = decoded_private_key
            log.debug("Decoding public key...")
            public_key = nacl_helper.decoded_public_key()
            log.debug(f"Public key {public_key} decoded!")
            data["public_key"] = public_key
            log.debug(f"Resulting data is: {data}")
        else:
            log.debug("Loading private and public keys...")
            private_key = PrivateKey(data["private_key"], encoder)
            public_key = data["public_key"]

        # Set host and port
        data["host"] = data.get("host", DEFAULT_HOST)
        data["port"] = data.get("port", DEFAULT_PORT)

        # Set default remotes
        log.debug("Setting default remotes...")
        default_remotes = [{"pattern": r"^https?\:\/\/localhost?(:[0-9]*)?"}]
        log.debug(f"Default remotes {default_remotes} set!")

        data["remotes"] = data.get("remotes", default_remotes)
        log.debug(f"Data is: {data}")
        log.debug(f"Loaded data is: {loaded_data}")
        log.debug(f"Data comparison is: {loaded_data != data}")
        # Save the updated data to the config file
        if loaded_data != data:
            log.info("Saving the updated data to the config file...")
            with open(file_path, "w", encoding="utf-8") as config_file:
                dump(data, config_file, indent=2)

        # Assign values to class attributes
        self.host = data["host"]
        self.port = data["port"]
        self.remotes = [
            compile(remote["pattern"]) if "pattern" in remote else remote
            for remote in data["remotes"]
        ]
        self.ssl = data.get("ssl", None)
        self.private_key = private_key
        self.public_key = public_key
