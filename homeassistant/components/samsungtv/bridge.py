"""samsungctl and samsungtvws bridge classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from collections.abc import Callable, Iterable, Mapping
import contextlib
from datetime import datetime, timedelta
from typing import Any, cast

from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, ConnectionClosed, UnhandledResponse
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.async_rest import SamsungTVAsyncRest
from samsungtvws.command import SamsungTVCommand
from samsungtvws.encrypted.command import SamsungTVEncryptedCommand
from samsungtvws.encrypted.remote import (
    SamsungTVEncryptedWSAsyncRemote,
    SendRemoteKey as SendEncryptedRemoteKey,
)
from samsungtvws.event import (
    ED_INSTALLED_APP_EVENT,
    MS_ERROR_EVENT,
    parse_installed_app,
)
from samsungtvws.exceptions import (
    ConnectionFailure,
    HttpApiError,
    ResponseError,
    UnauthorizedError,
)
from samsungtvws.remote import ChannelEmitCommand, SendRemoteKey
from websockets.exceptions import ConnectionClosedError, WebSocketException

from homeassistant.const import (
    CONF_DESCRIPTION,
    CONF_HOST,
    CONF_ID,
    CONF_METHOD,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TOKEN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import entity_component
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SESSION_ID,
    ENCRYPTED_WEBSOCKET_PORT,
    LEGACY_PORT,
    LOGGER,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    SUCCESSFUL_RESULTS,
    TIMEOUT_REQUEST,
    TIMEOUT_WEBSOCKET,
    VALUE_CONF_ID,
    VALUE_CONF_NAME,
    WEBSOCKET_PORTS,
)

# Since the TV will take a few seconds to go to sleep
# and actually be seen as off, we need to wait just a bit
# more than the next scan interval
SCAN_INTERVAL_PLUS_OFF_TIME = entity_component.DEFAULT_SCAN_INTERVAL + timedelta(
    seconds=5
)

KEY_PRESS_TIMEOUT = 1.2

ENCRYPTED_MODEL_USES_POWER_OFF = {"H6400", "H6410"}
ENCRYPTED_MODEL_USES_POWER = {"JU6400", "JU641D"}

REST_EXCEPTIONS = (HttpApiError, AsyncioTimeoutError, ResponseError)


def mac_from_device_info(info: dict[str, Any]) -> str | None:
    """Extract the mac address from the device info."""
    if wifi_mac := info.get("device", {}).get("wifiMac"):
        return format_mac(wifi_mac)
    return None


def model_requires_encryption(model: str | None) -> bool:
    """H and J models need pairing with PIN."""
    return model is not None and len(model) > 4 and model[4] in ("H", "J")


async def async_get_device_info(
    hass: HomeAssistant,
    host: str,
) -> tuple[str, int | None, str | None, dict[str, Any] | None]:
    """Fetch the port, method, and device info."""
    # Try the websocket ssl and non-ssl ports
    for port in WEBSOCKET_PORTS:
        bridge = SamsungTVBridge.get_bridge(hass, METHOD_WEBSOCKET, host, port)
        if info := await bridge.async_device_info():
            LOGGER.debug(
                "Fetching rest info via %s was successful: %s, checking for encrypted",
                port,
                info,
            )
            # Check the encrypted port if the model requires encryption
            if model_requires_encryption(info.get("device", {}).get("modelName")):
                encrypted_bridge = SamsungTVEncryptedBridge(
                    hass, METHOD_ENCRYPTED_WEBSOCKET, host, ENCRYPTED_WEBSOCKET_PORT
                )
                result = await encrypted_bridge.async_try_connect()
                if result != RESULT_CANNOT_CONNECT:
                    return (
                        result,
                        ENCRYPTED_WEBSOCKET_PORT,
                        METHOD_ENCRYPTED_WEBSOCKET,
                        info,
                    )
            return RESULT_SUCCESS, port, METHOD_WEBSOCKET, info

    # Try legacy port
    bridge = SamsungTVBridge.get_bridge(hass, METHOD_LEGACY, host, LEGACY_PORT)
    result = await bridge.async_try_connect()
    if result in SUCCESSFUL_RESULTS:
        return result, LEGACY_PORT, METHOD_LEGACY, await bridge.async_device_info()

    # Failed to get info
    return result, None, None, None


class SamsungTVBridge(ABC):
    """The Base Bridge abstract class."""

    @staticmethod
    def get_bridge(
        hass: HomeAssistant,
        method: str,
        host: str,
        port: int | None = None,
        entry_data: Mapping[str, Any] | None = None,
    ) -> SamsungTVBridge:
        """Get Bridge instance."""
        if method == METHOD_LEGACY or port == LEGACY_PORT:
            return SamsungTVLegacyBridge(
                hass, method, host, LEGACY_PORT if port is None else port
            )
        if method == METHOD_ENCRYPTED_WEBSOCKET or port == ENCRYPTED_WEBSOCKET_PORT:
            return SamsungTVEncryptedBridge(hass, method, host, port, entry_data)
        return SamsungTVWSBridge(hass, method, host, port, entry_data)

    def __init__(
        self, hass: HomeAssistant, method: str, host: str, port: int | None = None
    ) -> None:
        """Initialize Bridge."""
        self.hass = hass
        self.port = port
        self.method = method
        self.host = host
        self.token: str | None = None
        self.session_id: str | None = None
        self.auth_failed: bool = False
        self._reauth_callback: CALLBACK_TYPE | None = None
        self._update_config_entry: Callable[[Mapping[str, Any]], None] | None = None
        self._app_list_callback: Callable[[dict[str, str]], None] | None = None

        # Mark the end of a shutdown command (need to wait 15 seconds before
        # sending the next command to avoid turning the TV back ON).
        self._end_of_power_off: datetime | None = None

    def register_reauth_callback(self, func: CALLBACK_TYPE) -> None:
        """Register a callback function."""
        self._reauth_callback = func

    def register_update_config_entry_callback(
        self, func: Callable[[Mapping[str, Any]], None]
    ) -> None:
        """Register a callback function."""
        self._update_config_entry = func

    def register_app_list_callback(
        self, func: Callable[[dict[str, str]], None]
    ) -> None:
        """Register app_list callback function."""
        self._app_list_callback = func

    @abstractmethod
    async def async_try_connect(self) -> str:
        """Try to connect to the TV."""

    @abstractmethod
    async def async_device_info(self) -> dict[str, Any] | None:
        """Try to gather infos of this TV."""

    async def async_request_app_list(self) -> None:
        """Request app list."""
        # Overridden in SamsungTVWSBridge
        LOGGER.debug(
            "App list request is not supported on %s TV: %s",
            self.method,
            self.host,
        )
        self._notify_app_list_callback({})

    @abstractmethod
    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""

    @abstractmethod
    async def async_send_keys(self, keys: list[str]) -> None:
        """Send a list of keys to the tv."""

    @property
    def power_off_in_progress(self) -> bool:
        """Return if power off has been recently requested."""
        return (
            self._end_of_power_off is not None
            and self._end_of_power_off > dt_util.utcnow()
        )

    async def async_power_off(self) -> None:
        """Send power off command to remote and close."""
        self._end_of_power_off = dt_util.utcnow() + SCAN_INTERVAL_PLUS_OFF_TIME
        await self._async_send_power_off()
        # Force closing of remote session to provide instant UI feedback
        await self.async_close_remote()

    @abstractmethod
    async def _async_send_power_off(self) -> None:
        """Send power off command."""

    @abstractmethod
    async def async_close_remote(self) -> None:
        """Close remote object."""

    def _notify_reauth_callback(self) -> None:
        """Notify access denied callback."""
        if self._reauth_callback is not None:
            self._reauth_callback()

    def _notify_update_config_entry(self, updates: Mapping[str, Any]) -> None:
        """Notify update config callback."""
        if self._update_config_entry is not None:
            self._update_config_entry(updates)

    def _notify_app_list_callback(self, app_list: dict[str, str]) -> None:
        """Notify update config callback."""
        if self._app_list_callback is not None:
            self._app_list_callback(app_list)


class SamsungTVLegacyBridge(SamsungTVBridge):
    """The Bridge for Legacy TVs."""

    def __init__(
        self, hass: HomeAssistant, method: str, host: str, port: int | None
    ) -> None:
        """Initialize Bridge."""
        super().__init__(hass, method, host, port)
        self.config = {
            CONF_NAME: VALUE_CONF_NAME,
            CONF_DESCRIPTION: VALUE_CONF_NAME,
            CONF_ID: VALUE_CONF_ID,
            CONF_HOST: host,
            CONF_METHOD: method,
            CONF_PORT: port,
            CONF_TIMEOUT: 1,
        }
        self._remote: Remote | None = None

    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""
        return await self.hass.async_add_executor_job(self._is_on)

    def _is_on(self) -> bool:
        """Tells if the TV is on."""
        if self._remote is not None:
            self._close_remote()

        try:
            return self._get_remote() is not None
        except (UnhandledResponse, AccessDenied):
            # We got a response so it's working.
            return True

    async def async_try_connect(self) -> str:
        """Try to connect to the Legacy TV."""
        return await self.hass.async_add_executor_job(self._try_connect)

    def _try_connect(self) -> str:
        """Try to connect to the Legacy TV."""
        config = {
            CONF_NAME: VALUE_CONF_NAME,
            CONF_DESCRIPTION: VALUE_CONF_NAME,
            CONF_ID: VALUE_CONF_ID,
            CONF_HOST: self.host,
            CONF_METHOD: self.method,
            CONF_PORT: self.port,
            # We need this high timeout because waiting for auth popup
            # is just an open socket
            CONF_TIMEOUT: TIMEOUT_REQUEST,
        }
        try:
            LOGGER.debug("Try config: %s", config)
            with Remote(config.copy()):
                LOGGER.debug("Working config: %s", config)
                return RESULT_SUCCESS
        except AccessDenied:
            LOGGER.debug("Working but denied config: %s", config)
            return RESULT_AUTH_MISSING
        except UnhandledResponse as err:
            LOGGER.debug("Working but unsupported config: %s, error: %s", config, err)
            return RESULT_NOT_SUPPORTED
        except (ConnectionClosed, OSError) as err:
            LOGGER.debug("Failing config: %s, error: %s", config, err)
            return RESULT_CANNOT_CONNECT

    async def async_device_info(self) -> dict[str, Any] | None:
        """Try to gather infos of this device."""
        return None

    def _notify_reauth_callback(self) -> None:
        """Notify access denied callback."""
        if self._reauth_callback is not None:
            self.hass.loop.call_soon_threadsafe(self._reauth_callback)

    def _get_remote(self) -> Remote:
        """Create or return a remote control instance."""
        if self._remote is None:
            # We need to create a new instance to reconnect.
            try:
                LOGGER.debug("Create SamsungTVLegacyBridge for %s", self.host)
                self._remote = Remote(self.config.copy())
            # This is only happening when the auth was switched to DENY
            # A removed auth will lead to socket timeout because waiting
            # for auth popup is just an open socket
            except AccessDenied:
                self.auth_failed = True
                self._notify_reauth_callback()
                raise
            except (ConnectionClosed, OSError):
                pass
        return self._remote

    async def async_send_keys(self, keys: list[str]) -> None:
        """Send a list of keys using legacy protocol."""
        first_key = True
        for key in keys:
            if first_key:
                first_key = False
            else:
                await asyncio.sleep(KEY_PRESS_TIMEOUT)
            await self.hass.async_add_executor_job(self._send_key, key)

    def _send_key(self, key: str) -> None:
        """Send a key using legacy protocol."""
        try:
            # recreate connection if connection was dead
            retry_count = 1
            for _ in range(retry_count + 1):
                try:
                    if remote := self._get_remote():
                        remote.control(key)
                    break
                except (ConnectionClosed, BrokenPipeError):
                    # BrokenPipe can occur when the commands is sent to fast
                    self._remote = None
        except (UnhandledResponse, AccessDenied):
            # We got a response so it's on.
            LOGGER.debug("Failed sending command %s", key, exc_info=True)
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            pass

    async def _async_send_power_off(self) -> None:
        """Send power off command to remote."""
        await self.async_send_keys(["KEY_POWEROFF"])

    async def async_close_remote(self) -> None:
        """Close remote object."""
        await self.hass.async_add_executor_job(self._close_remote)

    def _close_remote(self) -> None:
        """Close remote object."""
        try:
            if self._remote is not None:
                # Close the current remote connection
                self._remote.close()
            self._remote = None
        except OSError:
            LOGGER.debug("Could not establish connection")


class SamsungTVWSBaseBridge[
    _RemoteT: (SamsungTVWSAsyncRemote, SamsungTVEncryptedWSAsyncRemote),
    _CommandT: (SamsungTVCommand, SamsungTVEncryptedCommand),
](SamsungTVBridge):
    """The Bridge for WebSocket TVs (v1/v2)."""

    def __init__(
        self,
        hass: HomeAssistant,
        method: str,
        host: str,
        port: int | None = None,
    ) -> None:
        """Initialize Bridge."""
        super().__init__(hass, method, host, port)
        self._remote: _RemoteT | None = None
        self._remote_lock = asyncio.Lock()

    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""
        LOGGER.debug("Checking if TV %s is on using websocket", self.host)
        if remote := await self._async_get_remote():
            return remote.is_alive()
        return False

    async def _async_send_commands(self, commands: list[_CommandT]) -> None:
        """Send the commands using websocket protocol."""
        try:
            # recreate connection if connection was dead
            retry_count = 1
            for _ in range(retry_count + 1):
                try:
                    if remote := await self._async_get_remote():
                        await remote.send_commands(commands)  # type: ignore[arg-type]
                    break
                except (
                    BrokenPipeError,
                    WebSocketException,
                ):
                    # BrokenPipe can occur when the commands is sent to fast
                    # WebSocketException can occur when timed out
                    self._remote = None
        except OSError:
            # Different reasons, e.g. hostname not resolveable
            pass

    async def _async_get_remote(self) -> _RemoteT | None:
        """Create or return a remote control instance."""
        if (remote := self._remote) and remote.is_alive():
            # If we have one then try to use it
            return remote

        async with self._remote_lock:
            # If we don't have one make sure we do it under the lock
            # so we don't make two do due a race to get the remote
            return await self._async_get_remote_under_lock()

    @abstractmethod
    async def _async_get_remote_under_lock(self) -> _RemoteT | None:
        """Create or return a remote control instance."""

    async def async_close_remote(self) -> None:
        """Close remote object."""
        try:
            if self._remote is not None:
                # Close the current remote connection
                await self._remote.close()
            self._remote = None
        except OSError as err:
            LOGGER.debug("Error closing connection to %s: %s", self.host, err)


class SamsungTVWSBridge(
    SamsungTVWSBaseBridge[SamsungTVWSAsyncRemote, SamsungTVCommand]
):
    """The Bridge for WebSocket TVs (v2)."""

    def __init__(
        self,
        hass: HomeAssistant,
        method: str,
        host: str,
        port: int | None = None,
        entry_data: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize Bridge."""
        super().__init__(hass, method, host, port)
        if entry_data:
            self.token = entry_data.get(CONF_TOKEN)
        self._rest_api: SamsungTVAsyncRest | None = None
        self._device_info: dict[str, Any] | None = None

    def _get_device_spec(self, key: str) -> Any | None:
        """Check if a flag exists in latest device info."""
        if not ((info := self._device_info) and (device := info.get("device"))):
            return None
        return device.get(key)

    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""
        # On some TVs, opening a websocket turns on the TV
        # so first check "PowerState" if device_info has it
        # then fallback to default, trying to open a websocket
        if self._get_device_spec("PowerState") is not None:
            LOGGER.debug("Checking if TV %s is on using device info", self.host)
            # Ensure we get an updated value
            info = await self.async_device_info(force=True)
            return info is not None and info["device"]["PowerState"] == "on"

        return await super().async_is_on()

    async def async_try_connect(self) -> str:
        """Try to connect to the Websocket TV."""
        for self.port in WEBSOCKET_PORTS:
            config = {
                CONF_NAME: VALUE_CONF_NAME,
                CONF_HOST: self.host,
                CONF_METHOD: self.method,
                CONF_PORT: self.port,
                # We need this high timeout because waiting for auth popup
                # is just an open socket
                CONF_TIMEOUT: TIMEOUT_REQUEST,
            }

            result = None
            try:
                LOGGER.debug("Try config: %s", config)
                async with SamsungTVWSAsyncRemote(
                    host=self.host,
                    port=self.port,
                    token=self.token,
                    timeout=TIMEOUT_REQUEST,
                    name=VALUE_CONF_NAME,
                ) as remote:
                    await remote.open()
                    self.token = remote.token
                    LOGGER.debug("Working config: %s", config)
                    return RESULT_SUCCESS
            except ConnectionClosedError as err:
                LOGGER.warning(
                    (
                        "Working but unsupported config: %s, error: '%s'; this may be"
                        " an indication that access to the TV has been denied. Please"
                        " check the Device Connection Manager on your TV"
                    ),
                    config,
                    err,
                )
                result = RESULT_NOT_SUPPORTED
            except WebSocketException as err:
                LOGGER.debug(
                    "Working but unsupported config: %s, error: %s", config, err
                )
                result = RESULT_NOT_SUPPORTED
            except UnauthorizedError as err:
                LOGGER.debug("Failing config: %s, %s error: %s", config, type(err), err)
                return RESULT_AUTH_MISSING
            except (ConnectionFailure, OSError, AsyncioTimeoutError) as err:
                LOGGER.debug("Failing config: %s, %s error: %s", config, type(err), err)
        else:  # noqa: PLW0120
            if result:
                return result

        return RESULT_CANNOT_CONNECT

    async def async_device_info(self, force: bool = False) -> dict[str, Any] | None:
        """Try to gather infos of this TV."""
        if self._rest_api is None:
            assert self.port
            self._rest_api = SamsungTVAsyncRest(
                host=self.host,
                session=async_get_clientsession(self.hass),
                port=self.port,
                timeout=TIMEOUT_WEBSOCKET,
            )

        try:
            device_info: dict[str, Any] = await self._rest_api.rest_device_info()
            LOGGER.debug("Device info on %s is: %s", self.host, device_info)
            self._device_info = device_info
        except REST_EXCEPTIONS as err:
            LOGGER.debug(
                "Failed to load device info from %s:%s: %s",
                self.host,
                self.port,
                str(err),
            )
        else:
            return device_info

        return None if force else self._device_info

    async def async_launch_app(self, app_id: str) -> None:
        """Send the launch_app command using websocket protocol."""
        await self._async_send_commands([ChannelEmitCommand.launch_app(app_id)])

    async def async_request_app_list(self) -> None:
        """Get installed app list."""
        await self._async_send_commands([ChannelEmitCommand.get_installed_app()])

    async def async_send_keys(self, keys: list[str]) -> None:
        """Send a list of keys using websocket protocol."""
        await self._async_send_commands([SendRemoteKey.click(key) for key in keys])

    async def _async_get_remote_under_lock(self) -> SamsungTVWSAsyncRemote | None:
        """Create or return a remote control instance."""
        if self._remote is None or not self._remote.is_alive():
            # We need to create a new instance to reconnect.
            LOGGER.debug("Create SamsungTVWSBridge for %s", self.host)
            assert self.port
            self._remote = SamsungTVWSAsyncRemote(
                host=self.host,
                port=self.port,
                token=self.token,
                timeout=TIMEOUT_WEBSOCKET,
                name=VALUE_CONF_NAME,
            )
            try:
                await self._remote.start_listening(self._remote_event)
            except UnauthorizedError as err:
                LOGGER.warning(
                    "Failed to get remote for %s, re-authentication required: %s",
                    self.host,
                    repr(err),
                )
                self.auth_failed = True
                self._notify_reauth_callback()
                self._remote = None
            except ConnectionClosedError as err:
                LOGGER.warning(
                    "Failed to get remote for %s: %s",
                    self.host,
                    repr(err),
                )
                self._remote = None
            except ConnectionFailure as err:
                LOGGER.warning(
                    (
                        "Unexpected ConnectionFailure trying to get remote for %s, "
                        "please report this issue: %s"
                    ),
                    self.host,
                    repr(err),
                )
                self._remote = None
            except (WebSocketException, AsyncioTimeoutError, OSError) as err:
                LOGGER.debug("Failed to get remote for %s: %s", self.host, repr(err))
                self._remote = None
            else:
                LOGGER.debug("Created SamsungTVWSBridge for %s", self.host)
                if self._device_info is None:
                    # Initialise device info on first connect
                    await self.async_device_info()
                if self.token != self._remote.token:
                    LOGGER.warning(
                        "SamsungTVWSBridge has provided a new token %s",
                        self._remote.token,
                    )
                    self.token = self._remote.token
                    self._notify_update_config_entry({CONF_TOKEN: self.token})
        return self._remote

    def _remote_event(self, event: str, response: Any) -> None:
        """Received event from remote websocket."""
        if event == ED_INSTALLED_APP_EVENT:
            self._notify_app_list_callback(
                {
                    app["name"]: app["appId"]
                    for app in sorted(
                        parse_installed_app(response),
                        key=lambda app: cast(str, app["name"]),
                    )
                }
            )
            return
        if event == MS_ERROR_EVENT:
            # { 'event': 'ms.error',
            #   'data': {'message': 'unrecognized method value : ms.remote.control'}}
            if (data := response.get("data")) and (
                message := data.get("message")
            ) == "unrecognized method value : ms.remote.control":
                LOGGER.error(
                    (
                        "Your TV seems to be unsupported by SamsungTVWSBridge"
                        " and needs a PIN: '%s'. Updating config entry"
                    ),
                    message,
                )
                self._notify_update_config_entry(
                    {
                        CONF_METHOD: METHOD_ENCRYPTED_WEBSOCKET,
                        CONF_PORT: ENCRYPTED_WEBSOCKET_PORT,
                    }
                )

    async def _async_send_power_off(self) -> None:
        """Send power off command to remote."""
        if self._get_device_spec("FrameTVSupport") == "true":
            await self._async_send_commands(SendRemoteKey.hold("KEY_POWER", 3))
        else:
            await self._async_send_commands([SendRemoteKey.click("KEY_POWER")])


class SamsungTVEncryptedBridge(
    SamsungTVWSBaseBridge[SamsungTVEncryptedWSAsyncRemote, SamsungTVEncryptedCommand]
):
    """The Bridge for Encrypted WebSocket TVs (v1 - J/H models)."""

    def __init__(
        self,
        hass: HomeAssistant,
        method: str,
        host: str,
        port: int | None = None,
        entry_data: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize Bridge."""
        super().__init__(hass, method, host, port)
        self._power_off_warning_logged: bool = False
        self._model: str | None = None
        self._short_model: str | None = None
        if entry_data:
            self.token = entry_data.get(CONF_TOKEN)
            self.session_id = entry_data.get(CONF_SESSION_ID)
            self._model = entry_data.get(CONF_MODEL)
            if self._model and len(self._model) > 4:
                self._short_model = self._model[4:]

        self._rest_api_port: int | None = None
        self._device_info: dict[str, Any] | None = None

    async def async_try_connect(self) -> str:
        """Try to connect to the Websocket TV."""
        self.port = ENCRYPTED_WEBSOCKET_PORT
        config = {
            CONF_NAME: VALUE_CONF_NAME,
            CONF_HOST: self.host,
            CONF_METHOD: self.method,
            CONF_PORT: self.port,
            CONF_TIMEOUT: TIMEOUT_WEBSOCKET,
        }

        try:
            LOGGER.debug("Try config: %s", config)
            async with SamsungTVEncryptedWSAsyncRemote(
                host=self.host,
                port=self.port,
                web_session=async_get_clientsession(self.hass),
                token=self.token or "",
                session_id=self.session_id or "",
                timeout=TIMEOUT_REQUEST,
            ) as remote:
                await remote.start_listening()
        except WebSocketException as err:
            LOGGER.debug("Working but unsupported config: %s, error: %s", config, err)
            return RESULT_NOT_SUPPORTED
        except (OSError, AsyncioTimeoutError, ConnectionFailure) as err:
            LOGGER.debug("Failing config: %s, error: %s", config, err)
        else:
            LOGGER.debug("Working config: %s", config)
            return RESULT_SUCCESS

        return RESULT_CANNOT_CONNECT

    async def async_device_info(self) -> dict[str, Any] | None:
        """Try to gather infos of this TV."""
        # Default to try all ports
        rest_api_ports: Iterable[int] = WEBSOCKET_PORTS
        if self._rest_api_port:
            # We have already made a successful call to the REST api
            rest_api_ports = (self._rest_api_port,)

        for rest_api_port in rest_api_ports:
            assert self.port
            rest_api = SamsungTVAsyncRest(
                host=self.host,
                session=async_get_clientsession(self.hass),
                port=rest_api_port,
                timeout=TIMEOUT_WEBSOCKET,
            )

            with contextlib.suppress(*REST_EXCEPTIONS):
                device_info: dict[str, Any] = await rest_api.rest_device_info()
                LOGGER.debug("Device info on %s is: %s", self.host, device_info)
                self._device_info = device_info
                self._rest_api_port = rest_api_port
                return device_info

        return self._device_info

    async def async_send_keys(self, keys: list[str]) -> None:
        """Send a list of keys using websocket protocol."""
        await self._async_send_commands(
            [SendEncryptedRemoteKey.click(key) for key in keys]
        )

    async def _async_get_remote_under_lock(
        self,
    ) -> SamsungTVEncryptedWSAsyncRemote | None:
        """Create or return a remote control instance."""
        if self._remote is None or not self._remote.is_alive():
            # We need to create a new instance to reconnect.
            LOGGER.debug("Create SamsungTVEncryptedBridge for %s", self.host)
            assert self.port
            self._remote = SamsungTVEncryptedWSAsyncRemote(
                host=self.host,
                port=self.port,
                web_session=async_get_clientsession(self.hass),
                token=self.token or "",
                session_id=self.session_id or "",
                timeout=TIMEOUT_WEBSOCKET,
            )
            try:
                await self._remote.start_listening()
            except (WebSocketException, AsyncioTimeoutError, OSError) as err:
                LOGGER.debug("Failed to get remote for %s: %s", self.host, repr(err))
                self._remote = None
            else:
                LOGGER.debug("Created SamsungTVEncryptedBridge for %s", self.host)
        return self._remote

    async def _async_send_power_off(self) -> None:
        """Send power off command to remote."""
        power_off_commands: list[SamsungTVEncryptedCommand] = []
        if self._short_model in ENCRYPTED_MODEL_USES_POWER_OFF:
            power_off_commands.append(SendEncryptedRemoteKey.click("KEY_POWEROFF"))
        elif self._short_model in ENCRYPTED_MODEL_USES_POWER:
            power_off_commands.append(SendEncryptedRemoteKey.click("KEY_POWER"))
        else:
            if self._model and not self._power_off_warning_logged:
                LOGGER.warning(
                    (
                        "Unknown power_off command for %s (%s): sending KEY_POWEROFF"
                        " and KEY_POWER"
                    ),
                    self._model,
                    self.host,
                )
                self._power_off_warning_logged = True
            power_off_commands.append(SendEncryptedRemoteKey.click("KEY_POWEROFF"))
            power_off_commands.append(SendEncryptedRemoteKey.click("KEY_POWER"))
        await self._async_send_commands(power_off_commands)
