"""Bridge for WebSocket Samsung TVs."""

from abc import abstractmethod
import asyncio
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from collections.abc import Mapping
from typing import Any, cast, override

from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.async_rest import SamsungTVAsyncRest
from samsungtvws.command import SamsungTVCommand
from samsungtvws.encrypted.command import SamsungTVEncryptedCommand
from samsungtvws.encrypted.remote import SamsungTVEncryptedWSAsyncRemote
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
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    ENCRYPTED_WEBSOCKET_PORT,
    LOGGER,
    METHOD_ENCRYPTED_WEBSOCKET,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    TIMEOUT_REQUEST,
    TIMEOUT_WEBSOCKET,
    VALUE_CONF_NAME,
    WEBSOCKET_PORTS,
)
from .base import SamsungTVBridge

REST_EXCEPTIONS = (HttpApiError, AsyncioTimeoutError, ResponseError)


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

    @override
    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""
        LOGGER.debug("Checking if TV %s is on using websocket", self.host)
        if remote := await self._async_get_remote():
            return remote.is_alive()
        return False

    async def _async_send_commands(self, commands: list[_CommandT]) -> None:
        """Send the commands using websocket protocol."""
        try:
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
                    self._remote = None
        except OSError:
            pass

    async def _async_get_remote(self) -> _RemoteT | None:
        """Create or return a remote control instance."""
        if (remote := self._remote) and remote.is_alive():
            return remote

        async with self._remote_lock:
            return await self._async_get_remote_under_lock()

    @abstractmethod
    async def _async_get_remote_under_lock(self) -> _RemoteT | None:
        """Create or return a remote control instance."""

    @override
    async def async_close_remote(self) -> None:
        """Close remote object."""
        try:
            if self._remote is not None:
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

    @override
    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""
        if self._get_device_spec("PowerState") is not None:
            LOGGER.debug("Checking if TV %s is on using device info", self.host)
            info = await self.async_device_info(force=True)
            return info is not None and info["device"]["PowerState"] == "on"

        return await super().async_is_on()

    @override
    async def async_try_connect(self) -> str:
        """Try to connect to the Websocket TV."""
        temp_result = None
        for self.port in WEBSOCKET_PORTS:
            config = {
                CONF_NAME: VALUE_CONF_NAME,
                CONF_HOST: self.host,
                CONF_METHOD: self.method,
                CONF_PORT: self.port,
                CONF_TIMEOUT: TIMEOUT_REQUEST,
            }

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
                temp_result = RESULT_NOT_SUPPORTED
            except WebSocketException as err:
                LOGGER.debug(
                    "Working but unsupported config: %s, error: %s", config, err
                )
                temp_result = RESULT_NOT_SUPPORTED
            except UnauthorizedError as err:
                LOGGER.debug("Failing config: %s, %s error: %s", config, type(err), err)
                return RESULT_AUTH_MISSING
            except (ConnectionFailure, OSError, AsyncioTimeoutError) as err:
                LOGGER.debug("Failing config: %s, %s error: %s", config, type(err), err)

        return temp_result or RESULT_CANNOT_CONNECT

    @override
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

    @override
    async def async_request_app_list(self) -> None:
        """Get installed app list."""
        await self._async_send_commands([ChannelEmitCommand.get_installed_app()])

    @override
    async def async_send_keys(self, keys: list[str]) -> None:
        """Send a list of keys using websocket protocol."""
        await self._async_send_commands([SendRemoteKey.click(key) for key in keys])

    @override
    async def _async_get_remote_under_lock(self) -> SamsungTVWSAsyncRemote | None:
        """Create or return a remote control instance."""
        if self._remote is None or not self._remote.is_alive():
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
                if "ms.channel.timeOut" in (error_details := repr(err)):
                    LOGGER.debug(
                        "Channel timeout occurred trying to get remote for %s: %s",
                        self.host,
                        error_details,
                    )
                else:
                    LOGGER.warning(
                        "Unexpected ConnectionFailure trying to get remote for %s, "
                        "please report this issue: %s",
                        self.host,
                        error_details,
                    )
                self._remote = None
            except (WebSocketException, AsyncioTimeoutError, OSError) as err:
                LOGGER.debug("Failed to get remote for %s: %s", self.host, repr(err))
                self._remote = None
            else:
                LOGGER.debug("Created SamsungTVWSBridge for %s", self.host)
                if self._device_info is None:
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

    @override
    async def _async_send_power_off(self) -> None:
        """Send power off command to remote."""
        if self._get_device_spec("FrameTVSupport") == "true":
            await self._async_send_commands(SendRemoteKey.hold("KEY_POWER", 3))
        else:
            await self._async_send_commands([SendRemoteKey.click("KEY_POWER")])
