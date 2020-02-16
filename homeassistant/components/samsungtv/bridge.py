"""samsungctl and samsungtvws bridge classes."""
from abc import ABC, abstractmethod

import requests
from requests import RequestException
from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, ConnectionClosed, UnhandledResponse
from samsungtvws import SamsungTVWS
from websocket import WebSocketException

from .const import (
    LOGGER,
    RESULT_AUTH_MISSING,
    RESULT_NOT_SUCCESSFUL,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
)


class SamsungTVBridge(ABC):
    """The Base Bridge abstract class."""

    @staticmethod
    def get_bridge(config):
        """Get Bridge instance."""
        if config:
            if config["method"] == "legacy":
                return SamsungTVLegacyBridge(config)
            if config["method"] == "websocket":
                return SamsungTVWSBridge(config)
        return None

    def __init__(self, config):
        """Initialize Bridge."""
        self.port = None
        self.token = None
        self.config = config
        self.method = config["method"]
        self.host = config["host"]
        self._remote = None
        self._callback = None

    def register_reauth_callback(self, func):
        """Register a callback function."""
        self._callback = func

    @abstractmethod
    def try_connect(self, port):
        """Try to connect to the TV."""

    @abstractmethod
    def is_on(self):
        """Tells if the TV is on."""

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

    @abstractmethod
    def _send_key(self, key):
        """Send the key."""

    @abstractmethod
    def _get_remote(self):
        """Get Remote object."""

    def close_remote(self):
        """Close remote object."""
        self._get_remote().close()

    def _notify_callback(self):
        """Notify access denied callback."""
        if self._callback:
            self._callback()


class SamsungTVLegacyBridge(SamsungTVBridge):
    """The Bridge for Legacy TVs."""

    def __init__(self, config):
        """Initialize Bridge."""
        super().__init__(config)
        self.port = 55000

    def try_connect(self, port):
        """Try to connect to the Legacy TV."""
        if port is not None and port != self.port:
            return RESULT_NOT_SUCCESSFUL
        config = {
            "name": "HomeAssistant",
            "description": "HomeAssistant",
            "id": "ha.component.samsung",
            "host": self.host,
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
        except UnhandledResponse:
            LOGGER.debug("Working but unsupported config: %s", config)
            return RESULT_NOT_SUPPORTED
        except OSError as err:
            LOGGER.debug("Failing config: %s, error: %s", config, err)
            return RESULT_NOT_SUCCESSFUL

    def is_on(self):
        """Tells if the TV is on."""
        if self._remote is not None:
            # Close the current remote connection
            self._remote.close()
            self._remote = None

        try:
            self._get_remote()
            if self._remote:
                return True
        except (
            UnhandledResponse,
            AccessDenied,
        ):
            # We got a response so it's working.
            return True
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            return False

        return False

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

    def __init__(self, config):
        """Initialize Bridge."""
        super().__init__(config)
        self.config = config

    def try_connect(self, port):
        """Try to connect to the Websocket TV."""
        for self.port in (8001, 8002):
            if port is not None and port != self.port:
                continue
            config = {
                "name": "HomeAssistant",
                "description": "HomeAssistant",
                "host": self.host,
                "method": self.method,
                "port": self.port,
                # We need this high timeout because waiting for auth popup is just an open socket
                "timeout": 31,
                "token": self.token,
            }
            try:
                LOGGER.debug("Try config: %s", config)
                with SamsungTVWS(
                    host=self.host,
                    port=self.port,
                    token=self.token,
                    timeout=config["timeout"],
                    name=config["name"],
                ) as remote:
                    remote.open()
                LOGGER.debug("Working config: %s", config)
                LOGGER.debug("Token: %s", self.token)
                return RESULT_SUCCESS
            except WebSocketException:
                LOGGER.debug("Working but unsupported config: %s", config)
                return RESULT_NOT_SUPPORTED
            except (OSError, Exception) as err:  # pylint: disable=broad-except
                LOGGER.debug("Failing config: %s, error: %s", config, err)

        return RESULT_NOT_SUCCESSFUL

    def is_on(self):
        """Get TV state."""
        try:
            ping_url = f"http://{self.host}:8001/api/v2/"

            requests.get(ping_url, timeout=1)
            return True
        except RequestException:
            return False

    def _send_key(self, key):
        """Send the key using websocket protocol."""
        if key == "KEY_POWEROFF":
            key = "KEY_POWER"
        self._get_remote().send_key(key)

    def _get_remote(self):
        """Create or return a remote control instance."""
        if self._remote is None:
            # We need to create a new instance to reconnect.
            LOGGER.debug("Create SamsungTVWS")
            self._remote = SamsungTVWS(
                host=self.config["host"],
                port=self.config["port"],
                token=self.config["token"],
                timeout=self.config["timeout"],
                name=self.config["name"],
            )
            self._remote.open()
        return self._remote
