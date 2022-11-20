"""Support for Qingping binary sensors."""
from __future__ import annotations

from functools import partial
from typing import Optional

from qingping_ble import BinarySensorDeviceClass as QingpingBinarySensorDeviceClass

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.bluetooth import (
    binary_sensor_update_to_bluetooth_data_update,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

BINARY_SENSOR_DESCRIPTIONS = {
    QingpingBinarySensorDeviceClass.MOTION: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.MOTION,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    QingpingBinarySensorDeviceClass.LIGHT: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.LIGHT,
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    QingpingBinarySensorDeviceClass.DOOR: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.DOOR,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    QingpingBinarySensorDeviceClass.PROBLEM: BinarySensorEntityDescription(
        key=QingpingBinarySensorDeviceClass.PROBLEM,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Qingping BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(
        partial(
            binary_sensor_update_to_bluetooth_data_update,
            binary_sensor_descriptions=BINARY_SENSOR_DESCRIPTIONS,
        )
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            QingpingBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class QingpingBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[Optional[bool]]],
    BinarySensorEntity,
):
    """Representation of a Qingping binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
