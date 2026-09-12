"""Bridge for Encrypted WebSocket Samsung TVs."""

from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from collections.abc import Iterable, Mapping
import contextlib
from typing import Any, override

from samsungtvws.async_rest import SamsungTVAsyncRest
from samsungtvws.encrypted.command import SamsungTVEncryptedCommand
from samsungtvws.encrypted.remote import (
    SamsungTVEncryptedWSAsyncRemote,
    SendRemoteKey as SendEncryptedRemoteKey,
)
from samsungtvws.exceptions import ConnectionFailure
from websockets.exceptions import WebSocketException

from homeassistant.const import (
    CONF_HOST,
    CONF_METHOD,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CONF_SESSION_ID,
    ENCRYPTED_WEBSOCKET_PORT,
    LOGGER,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    TIMEOUT_REQUEST,
    TIMEOUT_WEBSOCKET,
    VALUE_CONF_NAME,
    WEBSOCKET_PORTS,
)
from .websocket import REST_EXCEPTIONS, SamsungTVWSBaseBridge

ENCRYPTED_MODEL_USES_POWER_OFF = {"H6400", "H6410"}
ENCRYPTED_MODEL_USES_POWER = {"JU6400", "JU641D"}


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

    @override
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

    @override
    async def async_device_info(self) -> dict[str, Any] | None:
        """Try to gather infos of this TV."""
        rest_api_ports: Iterable[int] = WEBSOCKET_PORTS
        if self._rest_api_port:
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

    @override
    async def async_send_keys(self, keys: list[str]) -> None:
        """Send a list of keys using websocket protocol."""
        await self._async_send_commands(
            [SendEncryptedRemoteKey.click(key) for key in keys]
        )

    @override
    async def _async_get_remote_under_lock(
        self,
    ) -> SamsungTVEncryptedWSAsyncRemote | None:
        """Create or return a remote control instance."""
        if self._remote is None or not self._remote.is_alive():
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

    @override
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
