"""The Victron Bluetooth Low Energy integration."""

from __future__ import annotations

import logging

from sensor_state_data import SensorUpdate
from victron_ble_ha_parser import VictronBluetoothDeviceData

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_rediscover_address,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import REAUTH_AFTER_FAILURES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    key = entry.data[CONF_ACCESS_TOKEN]
    data = VictronBluetoothDeviceData(key)
    consecutive_failures = 0

    def _update(
        service_info: BluetoothServiceInfoBleak,
    ) -> SensorUpdate:
        nonlocal consecutive_failures
        update = data.update(service_info)

        # If the device type was recognized (devices dict populated) but
        # only signal strength came back, decryption likely failed.
        # Unsupported devices have an empty devices dict and won't trigger this.
        if update.devices and len(update.entity_values) <= 1:
            consecutive_failures += 1
            if consecutive_failures >= REAUTH_AFTER_FAILURES:
                _LOGGER.debug(
                    "Triggering reauth for %s after %d consecutive failures",
                    address,
                    consecutive_failures,
                )
                entry.async_start_reauth(hass)
                consecutive_failures = 0
        else:
            consecutive_failures = 0

        return update

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update,
    )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )

    if unload_ok:
        async_rediscover_address(hass, entry.entry_id)

    return unload_ok
