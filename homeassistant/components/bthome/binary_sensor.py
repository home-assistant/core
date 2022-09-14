"""Support for BTHome binary sensors."""
from __future__ import annotations

from typing import Optional

from bthome_ble import (
    BinarySensorDeviceClass as BTHomeBinarySensorDeviceClass,
    SensorUpdate,
)

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import device_key_to_bluetooth_entity_key, sensor_device_info_to_hass

BINARY_SENSOR_DESCRIPTIONS = {
    BTHomeBinarySensorDeviceClass.BATTERY: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BTHomeBinarySensorDeviceClass.BATTERY_CHARGING: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BTHomeBinarySensorDeviceClass.CO: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.CO,
        device_class=BinarySensorDeviceClass.CO,
    ),
    BTHomeBinarySensorDeviceClass.COLD: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.COLD,
        device_class=BinarySensorDeviceClass.COLD,
    ),
    BTHomeBinarySensorDeviceClass.CONNECTIVITY: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.CONNECTIVITY,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BTHomeBinarySensorDeviceClass.DOOR: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.DOOR,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BTHomeBinarySensorDeviceClass.HEAT: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.HEAT,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    BTHomeBinarySensorDeviceClass.GARAGE_DOOR: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.GARAGE_DOOR,
        device_class=BinarySensorDeviceClass.GARAGE_DOOR,
    ),
    BTHomeBinarySensorDeviceClass.GAS: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.GAS,
        device_class=BinarySensorDeviceClass.GAS,
    ),
    BTHomeBinarySensorDeviceClass.GENERIC: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.GENERIC,
    ),
    BTHomeBinarySensorDeviceClass.LIGHT: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.LIGHT,
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    BTHomeBinarySensorDeviceClass.LOCK: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.LOCK,
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    BTHomeBinarySensorDeviceClass.MOISTURE: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.MOISTURE,
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BTHomeBinarySensorDeviceClass.MOTION: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    BTHomeBinarySensorDeviceClass.MOVING: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.MOVING,
        device_class=BinarySensorDeviceClass.MOVING,
    ),
    BTHomeBinarySensorDeviceClass.OCCUPANCY: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.OCCUPANCY,
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BTHomeBinarySensorDeviceClass.OPENING: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.OPENING,
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    BTHomeBinarySensorDeviceClass.PLUG: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.PLUG,
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BTHomeBinarySensorDeviceClass.POWER: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.POWER,
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BTHomeBinarySensorDeviceClass.PRESENCE: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.PRESENCE,
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    BTHomeBinarySensorDeviceClass.PROBLEM: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.PROBLEM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BTHomeBinarySensorDeviceClass.RUNNING: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BTHomeBinarySensorDeviceClass.SAFETY: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.SAFETY,
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BTHomeBinarySensorDeviceClass.SMOKE: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.SMOKE,
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    BTHomeBinarySensorDeviceClass.SOUND: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.SOUND,
        device_class=BinarySensorDeviceClass.SOUND,
    ),
    BTHomeBinarySensorDeviceClass.TAMPER: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    BTHomeBinarySensorDeviceClass.VIBRATION: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.VIBRATION,
        device_class=BinarySensorDeviceClass.VIBRATION,
    ),
    BTHomeBinarySensorDeviceClass.WINDOW: BinarySensorEntityDescription(
        key=BTHomeBinarySensorDeviceClass.WINDOW,
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a binary sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): BINARY_SENSOR_DESCRIPTIONS[
                description.device_class
            ]
            for device_key, description in sensor_update.binary_entity_descriptions.items()
            if description.device_class
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BTHome BLE binary sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            BTHomeBluetoothBinarySensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class BTHomeBluetoothBinarySensorEntity(
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[Optional[bool]]],
    BinarySensorEntity,
):
    """Representation of a BTHome binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
