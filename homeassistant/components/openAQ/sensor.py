from enum import Enum
from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

import homeassistant
from homeassistant.core import HomeAssistant
from dataclasses import dataclass
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

class OpenAQDeviceSensors(str, Enum):
    """Sensors to report in home assistant."""

    Last_Update = "TIMESTAMP"
    Air_Quality_index = "AQI"
    Particle_Matter_25 = "PM25"
    Particle_Matter_10 = "PM10"
    Particle_Matter_1 = "PM1"
    Concentration_of_Ozone = "OZONE"
    Atmospheric_Pressure = "ATMOSPHERIC_PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    Relative_humidity = "HUMIDITY"
    Concentration_of_Nitrogen_Dioxide = "NITROGEN_DIOXIDE"
    Concentration_of_NITROGEN_MONOXIDE = "NITROGEN_MONOXIDE"
    Concentration_of_Carbon_Monoxide = "CO"
    Concentration_of_Carbon_Dioxide = "CO2"
    Concentration_of_Sulphure_Dioxide = "SULPHUR_DIOXIDE"

@dataclass
class OpenAQSensorDescription(SensorEntityDescription):
    """Class to describe a Sensor entity."""

    metric: str | None = None


async def async_setup_entry(hass, entry, async_add_devices):
    """Configure the sensor platform."""
    entities = []
    hass.data[DOMAIN][entry.entry_id]

    entities.append(
        Station(
            hass,
            OpenAQSensorDescription(
                key="E_pres",
                name="Session Energy",
                metric="CO2",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ))
    async_add_devices(entities)

class Station(SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        description: OpenAQSensorDescription,
    ):
        self.entity_description = description
        # self._attr_unique_id = f"_{description}"
        # self._attributes: dict[str, str] = {}

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        return SensorDeviceClass.CO2

    @property
    def native_value(self):
        """Return the state of the sensor, rounding if a number."""
        return 1

    @property
    def native_unit_of_measurement(self):
        return "ppm"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        pass
