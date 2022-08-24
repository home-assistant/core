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
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ...helpers.typing import StateType
from ...helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN, VOLUME_BECQUEREL, VOLUME_PICOCURIE

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorEntityDescription] = {
    "radon_1day_avg": SensorEntityDescription(
        key="radon_1day_avg",
        native_unit_of_measurement=VOLUME_BECQUEREL,
        name="Radon 1-day average",
        icon="mdi:radioactive",
    ),
    "radon_longterm_avg": SensorEntityDescription(
        key="radon_longterm_avg",
        native_unit_of_measurement=VOLUME_BECQUEREL,
        name="Radon longterm average",
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
        native_unit_of_measurement=TEMP_CELSIUS,
        name="Temperature",
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        name="Humidity",
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_MBAR,
        name="Pressure",
    ),
    "battery": SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Battery",
    ),
    "co2": SensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="co2",
    ),
    "voc": SensorEntityDescription(
        key="voc",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        name="VOC",
        icon="mdi:cloud",
    ),
    "illuminance": SensorEntityDescription(
        key="illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        name="Illuminance",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airthings BLE sensors."""
    is_metric = hass.config.units.is_metric

    coordinator: DataUpdateCoordinator[AirthingsDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    # we need to change some units
    if not is_metric:
        for key, val in SENSORS.items():
            if val.native_unit_of_measurement is not VOLUME_BECQUEREL:
                continue
            SENSORS[key].native_unit_of_measurement = VOLUME_PICOCURIE

    entities = []
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors.keys())
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in SENSORS:
            _LOGGER.debug(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )
            continue
        entities.append(
            AirthingsSensor(coordinator, coordinator.data, SENSORS[sensor_type])
        )

    async_add_entities(entities)


class AirthingsSensor(
    CoordinatorEntity[DataUpdateCoordinator[AirthingsDevice]], SensorEntity
):
    """Airthings BLE sensors for the device."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
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
            identifiers={
                (
                    DOMAIN,
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
