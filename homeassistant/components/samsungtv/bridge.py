"""samsungctl and samsungtvws bridge classes."""
import os

from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, UnhandledResponse
from samsungtvws import SamsungTVWS
from websocket import WebSocketException

from .const import (
    LOGGER,
    RESULT_AUTH_MISSING,
    RESULT_NOT_SUCCESSFUL,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
)


class SamsungTVBridge:
    """The Base Bridge class."""

    def __init__(self):
        """Initialize Bridge."""
        self.port = None
        self.method = None
        self.token_file = None

    def try_connect(self, host, port):
        """Try to connect to the TV."""


class SamsungTVLegacyBridge(SamsungTVBridge):
    """The Bridge for Legacy TVs."""

    def __init__(self):
        """Initialize Bridge."""
        super().__init__()
        self.method = "legacy"
        self.port = 55000

    def try_connect(self, host, port):
        """Try to connect to the Legacy TV."""
        if port is None or port == self.port:
            config = {
                "name": "HomeAssistant",
                "description": "HomeAssistant",
                "id": "ha.component.samsung",
                "host": host,
                "method": self.method,
                "port": self.port,
                # We need this high timeout because waiting for auth popup is just an open socket
                "timeout": 31,
            }
            try:
                LOGGER.debug("Try config: %s", config)
                with Remote(config.copy()):
                    LOGGER.debug("Working config: %s", config)
                    return RESULT_SUCCESS
            except AccessDenied:
                LOGGER.debug("Working but denied config: %s", config)
                return RESULT_AUTH_MISSING
            except (UnhandledResponse):
                LOGGER.debug("Working but unsupported config: %s", config)
                return RESULT_NOT_SUPPORTED
            except OSError as err:
                LOGGER.debug("Failing config: %s, error: %s", config, err)

        return RESULT_NOT_SUCCESSFUL


class SamsungTVWSBridge(SamsungTVBridge):
    """The Bridge for WebSocket TVs."""

    def __init__(self, hass):
        """Initialize Bridge."""
        super().__init__()
        self.hass = hass
        self.method = "websocket"

    def _get_token_file(self, host):
        """Get Token file."""
        path = self.hass.config.path()
        token_file = f"{path}/.samsungtv-token-{host}.dat"

        if os.path.isfile(token_file) is False:
            # Create token file for catch possible errors
            try:
                handle = open(token_file, "w+")
                handle.close()
            except OSError:
                LOGGER.error("Samsung TV - Error creating token file: %s", token_file)
                token_file = None
        return token_file

    def try_connect(self, host, port):
        """Try to connect to the Websocket TV."""
        for self.port in (8001, 8002):
            if port is None or port == self.port:
                token_file = None
                if port == 8002:
                    token_file = self._get_token_file(host)
                config = {
                    "name": "HomeAssistant",
                    "description": "HomeAssistant",
                    "host": host,
                    "method": self.method,
                    "port": self.port,
                    # We need this high timeout because waiting for auth popup is just an open socket
                    "timeout": 31,
                    "token_file": token_file,
                }
                try:
                    LOGGER.debug("Try config: %s", config)
                    with SamsungTVWS(
                        host=host,
                        port=self.port,
                        token_file=token_file,
                        timeout=config["timeout"],
                        name=config["name"],
                    ) as remote:
                        remote.open()
                    LOGGER.debug("Working config: %s", config)
                    self.token_file = token_file
                    return RESULT_SUCCESS
                except WebSocketException:
                    LOGGER.debug("Working but unsupported config: %s", config)
                    return RESULT_NOT_SUPPORTED
                except (OSError, Exception) as err:  # pylint: disable=broad-except
                    LOGGER.debug("Failing config: %s, error: %s", config, err)

        return RESULT_NOT_SUCCESSFUL
