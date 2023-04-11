"""Sensor platform for Victron BLE."""

import logging

from sensor_state_data import DeviceKey

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


def _victron_state_class(device_key: DeviceKey):
    """Return the state class for a sensor."""
    key = device_key.key.lower()
    if "yield" in key:
        return SensorStateClass.TOTAL_INCREASING
    if "alarm" in key or "state" in key or "mode" in key:
        return None
    return SensorStateClass.MEASUREMENT


def sensor_update_to_bluetooth_data_update(sensor_update):
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            PassiveBluetoothEntityKey(
                device_key.key, device_key.device_id
            ): SensorEntityDescription(
                key=device_key.key,
                device_class=SensorDeviceClass(description.device_class.value)
                if description.device_class
                else SensorDeviceClass.ENUM,
                native_unit_of_measurement=description.native_unit_of_measurement,
                state_class=_victron_state_class(device_key),
            )
            for device_key, description in sensor_update.entity_descriptions.items()
        },
        entity_data={
            PassiveBluetoothEntityKey(
                device_key.key, device_key.device_id
            ): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            PassiveBluetoothEntityKey(
                device_key.key, device_key.device_id
            ): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Victron BLE sensor."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            VictronBLESensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class VictronBLESensorEntity(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of Victron BLE sensor."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.processor.entity_data.get(self.entity_key)
