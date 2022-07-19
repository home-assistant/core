"""The INKBIRD Bluetooth integration."""
from __future__ import annotations

import logging

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .data import INKBIRDBluetoothDeviceData

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class InkbirdDataUpdateCoordinator(PassiveBluetoothDataUpdateCoordinator[StateType]):
    """Coordinator for Govee Bluetooth data."""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up INKBIRD BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothDataUpdateCoordinator(
        hass,
        _LOGGER,
        data=INKBIRDBluetoothDeviceData(),
        name=entry.title,
        address=address,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_setup())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
