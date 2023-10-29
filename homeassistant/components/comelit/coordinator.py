"""Support for Comelit."""
from datetime import timedelta
from typing import Any

from aiocomelit import ComeliteSerialBridgeApi, ComelitSerialBridgeObject, exceptions
from aiocomelit.const import BRIDGE

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN


class ComelitSerialBridge(DataUpdateCoordinator):
    """Queries Comelit Serial Bridge."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, host: str, port: int, pin: int) -> None:
        """Initialize the scanner."""

        self._host = host
        self._port = port
        self._pin = pin

        self.api = ComeliteSerialBridgeApi(host, port, pin)

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=5),
        )
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            model=BRIDGE,
            name=f"{BRIDGE} ({self.api.host})",
            **self.basic_device_info,
        )

    @property
    def basic_device_info(self) -> dict:
        """Set basic device info."""

        return {
            "manufacturer": "Comelit",
            "hw_version": "20003101",
        }

    def platform_device_info(self, device: ComelitSerialBridgeObject) -> dr.DeviceInfo:
        """Set platform device info."""

        return dr.DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.config_entry.entry_id}-{device.type}-{device.index}")
            },
            via_device=(DOMAIN, self.config_entry.entry_id),
            name=device.name,
            model=f"{BRIDGE} {device.type}",
            **self.basic_device_info,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update device data."""
        _LOGGER.debug("Polling Comelit Serial Bridge host: %s", self._host)
        try:
            await self.api.login()
        except exceptions.CannotConnect as err:
            _LOGGER.warning("Connection error for %s", self._host)
            await self.api.close()
            raise UpdateFailed(f"Error fetching data: {repr(err)}") from err
        except exceptions.CannotAuthenticate:
            raise ConfigEntryAuthFailed

        return await self.api.get_all_devices()
