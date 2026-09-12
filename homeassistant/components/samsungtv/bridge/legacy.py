"""Bridge for Legacy Samsung TVs."""

import asyncio
from typing import Any, override

from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, ConnectionClosed, UnhandledResponse

from homeassistant.const import (
    CONF_DESCRIPTION,
    CONF_HOST,
    CONF_ID,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..const import (
    DOMAIN,
    LOGGER,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    TIMEOUT_REQUEST,
    VALUE_CONF_ID,
    VALUE_CONF_NAME,
)
from .base import SamsungTVBridge

KEY_PRESS_TIMEOUT = 1.2


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

    @override
    async def async_is_on(self) -> bool:
        """Tells if the TV is on."""
        return await self.hass.async_add_executor_job(self._is_on)

    def _is_on(self) -> bool:
        """Tells if the TV is on."""
        if self._remote is not None:
            self._close_remote()

        try:
            return self._get_remote() is not None
        except UnhandledResponse, AccessDenied:
            return True

    @override
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

    @override
    async def async_device_info(self) -> dict[str, Any] | None:
        """Try to gather infos of this device."""
        return None

    @override
    def _notify_reauth_callback(self) -> None:
        """Notify access denied callback."""
        if self._reauth_callback is not None:
            self.hass.loop.call_soon_threadsafe(self._reauth_callback)

    def _get_remote(self) -> Remote:
        """Create or return a remote control instance."""
        if self._remote is None:
            try:
                LOGGER.debug("Create SamsungTVLegacyBridge for %s", self.host)
                self._remote = Remote(self.config.copy())
            except AccessDenied:
                self.auth_failed = True
                self._notify_reauth_callback()
                raise
            except ConnectionClosed, OSError:
                pass
        return self._remote

    @override
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
            retry_count = 1
            for _ in range(retry_count + 1):
                try:
                    if remote := self._get_remote():
                        remote.control(key)
                    break
                except ConnectionClosed, BrokenPipeError:
                    self._remote = None
        except (UnhandledResponse, AccessDenied) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_sending_command",
                translation_placeholders={"error": repr(err), "host": self.host},
            ) from err
        except OSError:
            pass

    @override
    async def _async_send_power_off(self) -> None:
        """Send power off command to remote."""
        await self.async_send_keys(["KEY_POWEROFF"])

    @override
    async def async_close_remote(self) -> None:
        """Close remote object."""
        await self.hass.async_add_executor_job(self._close_remote)

    def _close_remote(self) -> None:
        """Close remote object."""
        try:
            if self._remote is not None:
                self._remote.close()
            self._remote = None
        except OSError:
            LOGGER.debug("Could not establish connection")
