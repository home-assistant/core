"""samsungctl and samsungtvws bridge classes."""
import os

import requests
from requests import RequestException
from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, ConnectionClosed, UnhandledResponse
from samsungtvws import SamsungTVWS
from websocket import WebSocketException

from homeassistant.const import STATE_OFF, STATE_ON

from .const import (
    LOGGER,
    RESULT_AUTH_MISSING,
    RESULT_NOT_SUCCESSFUL,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
)


class SamsungTVBridge:
    """The Base Bridge class."""

    @staticmethod
    def get_bridge(config):
        """Get Bridge instance."""
        if config:
            if config["method"] == "legacy":
                return SamsungTVLegacyBridge(config)
            if config["method"] == "websocket":
                return SamsungTVWSBridge(None, config)
        return None

    def __init__(self, config):
        """Initialize Bridge."""
        self.port = None
        self.method = None
        self.token_file = None
        self.config = None
        self._remote = None
        self._callback = None

    def register_reauth_callback(self, func):
        """Register a callback function."""
        self._callback = func

    def try_connect(self, host, port):
        """Try to connect to the TV."""

    def get_state(self, host):
        """Get TV state."""

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        try:
            # recreate connection if connection was dead
            retry_count = 1
            for _ in range(retry_count + 1):
                try:
                    self._send_key(key)
                    break
                except (
                    ConnectionClosed,
                    BrokenPipeError,
                    WebSocketException,
                ):
                    # BrokenPipe can occur when the commands is sent to fast
                    # WebSocketException can occur when timed out
                    self._remote = None
        except (UnhandledResponse, AccessDenied):
            # We got a response so it's on.
            LOGGER.debug("Failed sending command %s", key, exc_info=True)
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            pass

    def _send_key(self, key):
        """Send the key."""

    def _get_remote(self):
        """Get Remote object."""

    def close_remote(self):
        """Close remote object."""
        self._get_remote().close()

    def _notify_callback(self):
        if self._callback:
            self._callback()


class SamsungTVLegacyBridge(SamsungTVBridge):
    """The Bridge for Legacy TVs."""

    def __init__(self, config=None):
        """Initialize Bridge."""
        super().__init__(config)
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

    def get_state(self, host):
        """Get TV state."""
        if self._remote is not None:
            # Close the current remote connection
            self._remote.close()
            self._remote = None

        try:
            self._get_remote()
            if self._remote:
                return STATE_ON
        except (
            UnhandledResponse,
            AccessDenied,
        ):
            # We got a response so it's working.
            return STATE_ON
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            return STATE_OFF

        return STATE_OFF

    def _get_remote(self):
        """Create or return a remote control instance."""
        if self._remote is None:
            # We need to create a new instance to reconnect.
            try:
                LOGGER.debug("Create SamsungRemote")
                self._remote = Remote(self.config.copy())
            # This is only happening when the auth was switched to DENY
            # A removed auth will lead to socket timeout because waiting for auth popup is just an open socket
            except AccessDenied:
                self._notify_callback()
                raise
        return self._remote

    def _send_key(self, key):
        """Send the key using legacy protocol."""
        self._get_remote().control(key)


class SamsungTVWSBridge(SamsungTVBridge):
    """The Bridge for WebSocket TVs."""

    def __init__(self, hass, config=None):
        """Initialize Bridge."""
        super().__init__(config)
        self.hass = hass
        self.method = "websocket"
        self.config = config

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

    def get_state(self, host):
        """Get TV state."""
        try:
            ping_url = f"http://{host}:8001/api/v2/"

            requests.get(ping_url, timeout=1)
            return STATE_ON
        except RequestException:
            return STATE_OFF

    def _send_key(self, key):
        """Send the key using websocket protocol."""
        self._get_remote().send_key(key)

    def _get_remote(self):
        """Create or return a remote control instance."""
        if self._remote is None:
            # We need to create a new instance to reconnect.
            LOGGER.debug("Create SamsungTVWS")
            self._remote = SamsungTVWS(
                host=self.config["host"],
                port=self.config["port"],
                token_file=self.config["token_file"],
                timeout=self.config["timeout"],
                name=self.config["name"],
            )
            self._remote.open()
        return self._remote
