"""samsungctl and samsungtvws bridge classes."""
from abc import ABC, abstractmethod
import contextlib

from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, ConnectionClosed, UnhandledResponse
from samsungtvws import SamsungTVWS
from samsungtvws.exceptions import ConnectionFailure, HttpApiError
from websocket import WebSocketException

from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TOKEN,
)

from .const import (
    CONF_DESCRIPTION,
    LOGGER,
    METHOD_LEGACY,
    RESULT_AUTH_MISSING,
    RESULT_NOT_SUCCESSFUL,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    VALUE_CONF_ID,
    VALUE_CONF_NAME,
    WEBSOCKET_PORTS,
)


class SamsungTVBridge(ABC):
    """The Base Bridge abstract class."""

    @staticmethod
    def get_bridge(method, host, port=None, token=None):
        """Get Bridge instance."""
        if method == METHOD_LEGACY:
            return SamsungTVLegacyBridge(method, host, port)
        return SamsungTVWSBridge(method, host, port, token)

    def __init__(self, method, host, port):
        """Initialize Bridge."""
        self.port = port
        self.method = method
        self.host = host
        self.token = None
        self.default_port = None
        self._remote = None
        self._callback = None

    def register_reauth_callback(self, func):
        """Register a callback function."""
        self._callback = func

    @abstractmethod
    def try_connect(self):
        """Try to connect to the TV."""

    @abstractmethod
    def device_info(self):
        """Try to gather infos of this TV."""

    def is_on(self):
        """Tells if the TV is on."""
        self.close_remote()

        try:
            return self._get_remote() is not None
        except (
            UnhandledResponse,
            AccessDenied,
            ConnectionFailure,
        ):
            # We got a response so it's working.
            return True
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            return False

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
        try:
            if self._remote is not None:
                # Close the current remote connection
                self._remote.close()
            self._remote = None
        except OSError:
            LOGGER.debug("Could not establish connection")

    def _notify_callback(self):
        """Notify access denied callback."""
        if self._callback:
            self._callback()


class SamsungTVLegacyBridge(SamsungTVBridge):
    """The Bridge for Legacy TVs."""

    def __init__(self, method, host, port):
        """Initialize Bridge."""
        super().__init__(method, host, None)
        self.config = {
            CONF_NAME: VALUE_CONF_NAME,
            CONF_DESCRIPTION: VALUE_CONF_NAME,
            CONF_ID: VALUE_CONF_ID,
            CONF_HOST: host,
            CONF_METHOD: method,
            CONF_PORT: None,
            CONF_TIMEOUT: 1,
        }

    def try_connect(self):
        """Try to connect to the Legacy TV."""
        config = {
            CONF_NAME: VALUE_CONF_NAME,
            CONF_DESCRIPTION: VALUE_CONF_NAME,
            CONF_ID: VALUE_CONF_ID,
            CONF_HOST: self.host,
            CONF_METHOD: self.method,
            CONF_PORT: None,
            # We need this high timeout because waiting for auth popup is just an open socket
            CONF_TIMEOUT: 31,
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

    def device_info(self):
        """Try to gather infos of this device."""
        return None

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

    def stop(self):
        """Stop Bridge."""
        LOGGER.warning("Stopping SamsungRemote")
        self.close_remote()


class SamsungTVWSBridge(SamsungTVBridge):
    """The Bridge for WebSocket TVs."""

    def __init__(self, method, host, port, token=None):
        """Initialize Bridge."""
        super().__init__(method, host, port)
        self.token = token
        self.default_port = 8001

    def try_connect(self):
        """Try to connect to the Websocket TV."""
        for self.port in WEBSOCKET_PORTS:
            config = {
                CONF_NAME: VALUE_CONF_NAME,
                CONF_HOST: self.host,
                CONF_METHOD: self.method,
                CONF_PORT: self.port,
                # We need this high timeout because waiting for auth popup is just an open socket
                CONF_TIMEOUT: 31,
            }

            result = None
            try:
                LOGGER.debug("Try config: %s", config)
                with SamsungTVWS(
                    host=self.host,
                    port=self.port,
                    token=self.token,
                    timeout=config[CONF_TIMEOUT],
                    name=config[CONF_NAME],
                ) as remote:
                    remote.open()
                    self.token = remote.token
                    if self.token:
                        config[CONF_TOKEN] = "*****"
                LOGGER.debug("Working config: %s", config)
                return RESULT_SUCCESS
            except WebSocketException:
                LOGGER.debug("Working but unsupported config: %s", config)
                result = RESULT_NOT_SUPPORTED
            except (OSError, ConnectionFailure) as err:
                LOGGER.debug("Failing config: %s, error: %s", config, err)
        # pylint: disable=useless-else-on-loop
        else:
            if result:
                return result

        return RESULT_NOT_SUCCESSFUL

    def device_info(self):
        """Try to gather infos of this TV."""
        remote = self._get_remote()
        if not remote:
            return None
        with contextlib.suppress(HttpApiError):
            return remote.rest_device_info()

    def _send_key(self, key):
        """Send the key using websocket protocol."""
        if key == "KEY_POWEROFF":
            key = "KEY_POWER"
        self._get_remote().send_key(key)

    def _get_remote(self):
        """Create or return a remote control instance."""
        if self._remote is None:
            # We need to create a new instance to reconnect.
            try:
                LOGGER.debug("Create SamsungTVWS")
                self._remote = SamsungTVWS(
                    host=self.host,
                    port=self.port,
                    token=self.token,
                    timeout=8,
                    name=VALUE_CONF_NAME,
                )
                self._remote.open()
            # This is only happening when the auth was switched to DENY
            # A removed auth will lead to socket timeout because waiting for auth popup is just an open socket
            except ConnectionFailure:
                self._notify_callback()
            except (WebSocketException, OSError):
                self._remote = None
        return self._remote

    def stop(self):
        """Stop Bridge."""
        LOGGER.warning("Stopping SamsungTVWS")
        self.close_remote()
