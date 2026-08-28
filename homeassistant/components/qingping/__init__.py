"""The Qingping integration."""

import logging

from qingping_ble import QingpingBluetoothDeviceData

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CONNECTION_TYPE, CONNECTION_BLUETOOTH, CONNECTION_MQTT
from .coordinator import QingpingMqttCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type QingpingConfigEntry = ConfigEntry[
    PassiveBluetoothProcessorCoordinator | QingpingMqttCoordinator
]


async def async_setup_entry(hass: HomeAssistant, entry: QingpingConfigEntry) -> bool:
    """Set up Qingping from a config entry."""
    if entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_BLUETOOTH) == CONNECTION_MQTT:
        mqtt_coordinator = entry.runtime_data = QingpingMqttCoordinator(
            hass, entry, entry.data[CONF_MAC]
        )
        await mqtt_coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
        return True

    address = entry.unique_id
    assert address is not None
    data = QingpingBluetoothDeviceData()
    coordinator = entry.runtime_data = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=data.update,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QingpingConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
