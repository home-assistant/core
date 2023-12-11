"""Sensor platform for OpenAQ."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import homeassistant
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON_AIR, ICON_TIME, OPENAQ_PARAMETERS
from .coordinator import OpenAQDataCoordinator


class OpenAQDeviceSensors(str, Enum):
    """Sensors to report in home assistant."""

    Last_Update = SensorDeviceClass.TIMESTAMP
    Particle_Matter_25 = SensorDeviceClass.PM25
    Particle_Matter_10 = SensorDeviceClass.PM10
    Particle_Matter_1 = SensorDeviceClass.PM1
    Concentration_of_Ozone = SensorDeviceClass.OZONE
    Atmospheric_Pressure = SensorDeviceClass.ATMOSPHERIC_PRESSURE
    Temperature = SensorDeviceClass.TEMPERATURE
    Relative_humidity = SensorDeviceClass.HUMIDITY
    Concentration_of_Nitrogen_Dioxide = SensorDeviceClass.NITROGEN_DIOXIDE
    Concentration_of_Nitrogen_Monoxide = SensorDeviceClass.NITROGEN_MONOXIDE
    Concentration_of_Carbon_Monoxide = SensorDeviceClass.CO
    Concentration_of_Carbon_Dioxide = SensorDeviceClass.CO2
    Concentration_of_Sulphure_Dioxide = SensorDeviceClass.SULPHUR_DIOXIDE


@dataclass
class OpenAQSensorDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    metric: Enum | None = None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Configure the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = coordinator.get_sensors()
    sensor_names = [sensor.parameter.name for sensor in sensors]
    sensor_names.append(
        "last_update"
    )  # Special case for last updated as it is not available in get_sensors() but in the sensor data instead
    sensors_metrics = [
        OPENAQ_PARAMETERS[j] for j in sensor_names if j in OPENAQ_PARAMETERS
    ]

    entities = []

    for metric in sensors_metrics:
        match metric:
            case SensorDeviceClass.TIMESTAMP | SensorDeviceClass.AQI:
                unit = None
            case SensorDeviceClass.CO | SensorDeviceClass.CO2:
                unit = CONCENTRATION_PARTS_PER_MILLION
            case SensorDeviceClass.PM25 | SensorDeviceClass.PM10 | SensorDeviceClass.PM1 | SensorDeviceClass.OZONE | SensorDeviceClass.NITROGEN_DIOXIDE | SensorDeviceClass.NITROGEN_MONOXIDE | SensorDeviceClass.SULPHUR_DIOXIDE:
                unit = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
            case SensorDeviceClass.ATMOSPHERIC_PRESSURE:
                unit = UnitOfPressure.BAR
            case SensorDeviceClass.HUMIDITY:
                unit = PERCENTAGE
            case SensorDeviceClass.TEMPERATURE:
                unit = UnitOfTemperature.CELSIUS

        val_list = list(OPENAQ_PARAMETERS.values())
        key_list = list(OPENAQ_PARAMETERS.keys())

        metric_index = val_list.index(metric)

        entities.append(
            OpenAQSensor(
                hass,
                str(coordinator.client.get_device().id),
                OpenAQSensorDescription(
                    key=key_list[metric_index],
                    name=metric.name.replace("_", " "),
                    metric=metric,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    native_unit_of_measurement=unit,
                ),
                coordinator,
            ),
        )
    async_add_devices(entities)


class OpenAQSensor(CoordinatorEntity[OpenAQDataCoordinator], SensorEntity):
    """OpenAQ sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        station_id,
        description: OpenAQSensorDescription,
        coordinator: OpenAQDataCoordinator,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.entity_description = description
        self.station_id = station_id
        self.metric = self.entity_description.metric
        self._hass = hass
        self._last_reset = homeassistant.util.dt.utc_from_timestamp(0)
        self._attr_unique_id = ".".join(
            [DOMAIN, self.station_id, self.entity_description.key, SENSOR_DOMAIN]
        )
        self._attr_device_info = (
            DeviceInfo(  # Retrieve the same device added in __init__.py
                identifiers={(DOMAIN, self.station_id)},
            )
        )
        if self.metric == SensorDeviceClass.TIMESTAMP:
            self._attr_icon = ICON_TIME
        else:
            self._attr_icon = ICON_AIR

    @property
    def should_poll(self) -> bool:
        """Return True as entity has to be polled for state."""
        return False  # This is handled using the coordinator

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return None

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self.metric

    @property
    def native_value(self):
        """Return the state of the sensor, rounding if a number."""
        name = self.entity_description.key
        if self.metric == SensorDeviceClass.TIMESTAMP:
            return datetime.strptime(
                self.coordinator.data.get(name),
                "%Y-%m-%dT%H:%M:%S%z",  # The datetime from the response will be a string that needs to be converted
            )

        return self.coordinator.data.get(name)
