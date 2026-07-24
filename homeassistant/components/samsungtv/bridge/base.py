"""samsungctl and samsungtvws bridge base class."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import entity_component
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util import dt as dt_util

from ..const import (
    ENCRYPTED_WEBSOCKET_PORT,
    LEGACY_PORT,
    LOGGER,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
)

SCAN_INTERVAL_PLUS_OFF_TIME = entity_component.DEFAULT_SCAN_INTERVAL + timedelta(
    seconds=5
)


def mac_from_device_info(info: dict[str, Any]) -> str | None:
    """Extract the mac address from the device info."""
    if wifi_mac := info.get("device", {}).get("wifiMac"):
        return format_mac(wifi_mac)
    return None


def model_requires_encryption(model: str | None) -> bool:
    """H and J models need pairing with PIN."""
    return model is not None and len(model) > 4 and model[4] in ("H", "J")


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
            from .legacy import SamsungTVLegacyBridge  # noqa: PLC0415

            return SamsungTVLegacyBridge(hass, method, host, port or LEGACY_PORT)
        if method == METHOD_ENCRYPTED_WEBSOCKET or port == ENCRYPTED_WEBSOCKET_PORT:
            from .encrypted import SamsungTVEncryptedBridge  # noqa: PLC0415

            return SamsungTVEncryptedBridge(hass, method, host, port, entry_data)
        from .websocket import SamsungTVWSBridge  # noqa: PLC0415

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
