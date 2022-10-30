"""The hatchrest integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from bleak.exc import BleakError
from pyhatchbabyrest import PyHatchBabyRestAsync, connect_async

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up hatchrest from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address = entry.data["address"]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper())
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Hatch Rest device with address {address}"
        )

    hass.data[DOMAIN][entry.entry_id] = HatchRestCoordinator(
        hass, entry.unique_id, await connect_async(ble_device)
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HatchRestCoordinator(DataUpdateCoordinator):
    """Coordinator for interacting with a Hatch Rest device."""

    def __init__(
        self, hass: HomeAssistant, unique_id: str | None, device: PyHatchBabyRestAsync
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="hatchrest",
            update_interval=timedelta(seconds=30),
        )
        self.unique_id = unique_id
        self.device = device

    async def _async_update_data(self) -> None:
        """Get updated data from device."""
        try:
            async with async_timeout.timeout(10):
                await self.device.refresh_data()
        except TimeoutError as exc:
            raise UpdateFailed(
                "connection timed out while fetching data from device"
            ) from exc
        except BleakError as exc:
            raise UpdateFailed("failed getting data from device") from exc


class HatchRestEntity(CoordinatorEntity):
    """Base entity for a Hatch Rest device."""

    def __init__(
        self,
        coordinator: HatchRestCoordinator,
    ) -> None:
        """Initialize entity coordinator and id."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_unique_id = coordinator.unique_id

    @property
    def name(self):
        """Name of the Hatch Rest device."""
        return self._device.name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Provide info about the Hatch Rest device for all entities."""
        return (
            {
                "identifiers": {(DOMAIN, self.unique_id)},
                "name": super().name,
                "manufacturer": "Hatch",
                "model": "Rest",
            }
            if self.unique_id
            else {}
        )
