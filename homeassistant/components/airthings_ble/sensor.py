"""Support for airthings ble sensors."""
from __future__ import annotations

import logging

from airthings_ble import AirthingsDevice

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DOMAIN, VOLUME_BECQUEREL, VOLUME_PICOCURIE

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    "radon_1day_avg": SensorEntityDescription(
        key="radon_1day_avg",
        native_unit_of_measurement=VOLUME_BECQUEREL,
        name="Radon 1-day average",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radioactive",
    ),
    "radon_longterm_avg": SensorEntityDescription(
        key="radon_longterm_avg",
        native_unit_of_measurement=VOLUME_BECQUEREL,
        name="Radon longterm average",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radioactive",
    ),
    "radon_1day_level": SensorEntityDescription(
        key="radon_1day_level",
        name="Radon 1-day level",
        icon="mdi:radioactive",
    ),
    "radon_longterm_level": SensorEntityDescription(
        key="radon_longterm_level",
        name="Radon longterm level",
        icon="mdi:radioactive",
    ),
    "temperature": SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        name="Temperature",
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Humidity",
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        name="Pressure",
    ),
    "battery": SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Battery",
    ),
    "co2": SensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        name="co2",
    ),
    "voc": SensorEntityDescription(
        key="voc",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        name="VOC",
        icon="mdi:cloud",
    ),
    "illuminance": SensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        name="Illuminance",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airthings BLE sensors."""
    is_metric = hass.config.units is METRIC_SYSTEM

    coordinator: DataUpdateCoordinator[AirthingsDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    # we need to change some units
    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()
    if not is_metric:
        for val in sensors_mapping.values():
            if val.native_unit_of_measurement is not VOLUME_BECQUEREL:
                continue
            val.native_unit_of_measurement = VOLUME_PICOCURIE

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
            AirthingsSensor(coordinator, coordinator.data, sensors_mapping[sensor_type])
        )

    async_add_entities(entities)


class AirthingsSensor(
    CoordinatorEntity[DataUpdateCoordinator[AirthingsDevice]], SensorEntity
):
    """Airthings BLE sensors for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[AirthingsDevice],
        airthings_device: AirthingsDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the airthings entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{airthings_device.name} {airthings_device.identifier}"

        self._attr_unique_id = f"{name}_{entity_description.key}"

        self._id = airthings_device.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    airthings_device.address,
                )
            },
            name=name,
            manufacturer="Airthings",
            hw_version=airthings_device.hw_version,
            sw_version=airthings_device.sw_version,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key]
