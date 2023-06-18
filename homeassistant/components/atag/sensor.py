"""Initialization of ATAG One sensor platform."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, AtagEntity

SENSORS = {
    "Outside Temperature": "outside_temp",
    "Average Outside Temperature": "tout_avg",
    "Weather Status": "weather_status",
    "CH Water Pressure": "ch_water_pres",
    "CH Water Temperature": "ch_water_temp",
    "CH Return Temperature": "ch_return_temp",
    "Burning Hours": "burning_hours",
    "Flame": "rel_mod_level",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AtagSensor(coordinator, sensor) for sensor in SENSORS])


class AtagSensor(AtagEntity, SensorEntity):
    """Representation of a AtagOne Sensor."""

    def __init__(self, coordinator, sensor):
        """Initialize Atag sensor."""
        super().__init__(coordinator, SENSORS[sensor])
        self._attr_name = sensor
        if coordinator.data.report[self._id].sensorclass in (
            SensorDeviceClass.PRESSURE,
            SensorDeviceClass.TEMPERATURE,
        ):
            self._attr_device_class = coordinator.data.report[self._id].sensorclass
        if coordinator.data.report[self._id].measure in (
            UnitOfPressure.BAR,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            PERCENTAGE,
            UnitOfTime.HOURS,
        ):
            self._attr_native_unit_of_measurement = coordinator.data.report[
                self._id
            ].measure

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.report[self._id].state

    @property
    def icon(self):
        """Return icon."""
        return self.coordinator.data.report[self._id].icon
