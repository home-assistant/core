"""Support for Medcom BLE radiation monitor sensors."""

from __future__ import annotations

import logging

from medcom_ble import MedcomBleDevice

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, UNIT_CPM

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    "cpm": SensorEntityDescription(
        key="cpm",
        translation_key="cpm",
        native_unit_of_measurement=UNIT_CPM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Medcom BLE radiation monitor sensors."""

    coordinator: DataUpdateCoordinator[MedcomBleDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in SENSORS_MAPPING_TEMPLATE:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        entities.append(
            MedcomSensor(coordinator, SENSORS_MAPPING_TEMPLATE[sensor_type])
        )

    async_add_entities(entities)


class MedcomSensor(
    CoordinatorEntity[DataUpdateCoordinator[MedcomBleDevice]], SensorEntity
):
    """Medcom BLE radiation monitor sensors for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[MedcomBleDevice],
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the medcom entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        medcom_device = coordinator.data

        name = medcom_device.name
        if identifier := medcom_device.identifier:
            name += f" ({identifier})"

        self._attr_unique_id = f"{medcom_device.address}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    medcom_device.address,
                )
            },
            name=name,
            manufacturer=medcom_device.manufacturer,
            hw_version=medcom_device.hw_version,
            sw_version=medcom_device.sw_version,
            model=medcom_device.model,
        )

    @property
    def native_value(self) -> float:
        """Return the value reported by the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key]
