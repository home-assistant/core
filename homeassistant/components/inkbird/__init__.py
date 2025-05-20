"""The INKBIRD Bluetooth integration."""

from __future__ import annotations

import logging

from inkbird_ble import INKBIRDBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DEVICE_TYPE, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up INKBIRD BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    device_type: str | None = entry.data.get(CONF_DEVICE_TYPE)
    data = INKBIRDBluetoothDeviceData(device_type)

    @callback
    def _async_on_update(service_info: BluetoothServiceInfo) -> SensorUpdate:
        """Handle update callback from the passive BLE processor."""
        nonlocal device_type
        update = data.update(service_info)
        if device_type is None and data.device_type is not None:
            device_type_str = str(data.device_type)
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_DEVICE_TYPE: device_type_str}
            )
            device_type = device_type_str
        return update

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_async_on_update,
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
