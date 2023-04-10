"""The Victron Bluetooth Low Energy integration."""

from __future__ import annotations

import logging

from victron_ble_ha_parser import VictronBluetoothDeviceData

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_rediscover_address,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    key = entry.data[CONF_ACCESS_TOKEN]
    data = VictronBluetoothDeviceData(key)
    coordinator = hass.data.setdefault(DOMAIN, {})[entry.entry_id] = (
        PassiveBluetoothProcessorCoordinator(
            hass,
            _LOGGER,
            address=address,
            mode=BluetoothScanningMode.ACTIVE,
            update_method=data.update,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = False

    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, Platform.SENSOR
    )

    if unload_ok:
        async_rediscover_address(hass, entry.entry_id)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
