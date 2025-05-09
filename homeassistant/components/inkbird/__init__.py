"""The INKBIRD Bluetooth integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_DATA, CONF_DEVICE_TYPE
from .coordinator import INKBIRDActiveBluetoothProcessorCoordinator

INKBIRDConfigEntry = ConfigEntry[INKBIRDActiveBluetoothProcessorCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: INKBIRDConfigEntry) -> bool:
    """Set up INKBIRD BLE device from a config entry."""
    assert entry.unique_id is not None
    device_type: str | None = entry.data.get(CONF_DEVICE_TYPE)
    device_data: dict[str, Any] | None = entry.data.get(CONF_DEVICE_DATA)
    _LOGGER.debug("Setting up INKBIRD device %s", entry.unique_id)
    coordinator = INKBIRDActiveBluetoothProcessorCoordinator(
        hass, entry, device_type, device_data
    )
    await coordinator.async_init()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: INKBIRDConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
