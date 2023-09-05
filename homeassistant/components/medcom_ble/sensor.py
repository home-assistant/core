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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
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
        icon="mdi:radioactive",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Medcom BLE radiation monitor sensors."""

    coordinator: DataUpdateCoordinator[MedcomBleDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    # See the Airthings BLE integration: this template system
    # lets us change some units if we want to. We could use this
    # in the future to map CPMs to dose rate, but this depends
    # on the device calibration - the device only tells us the CPM.
    # Another approach would be to store the calibration value in
    # Home assistant directly as a configuration.
    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in sensors_mapping:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        entities.append(
            MedcomSensor(coordinator, coordinator.data, sensors_mapping[sensor_type])
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
        medcom_device: MedcomBleDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the medcom entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

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
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key]
