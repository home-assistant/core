"""Support for the OpenWeatherMap (OWM) service."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    ENTITY_NAME,
    FORECAST_COORDINATOR,
    MONITORED_CONDITIONS,
    SENSOR_TYPES,
    WEATHER_COORDINATOR,
)
from .forecast_update_coordinator import ForecastUpdateCoordinator
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    entity_name = domain_data[ENTITY_NAME]
    weather_coordinator = domain_data[WEATHER_COORDINATOR]
    forecast_coordinator = domain_data[FORECAST_COORDINATOR]
    monitored_conditions_str = domain_data[MONITORED_CONDITIONS]

    monitored_conditions = str(monitored_conditions_str).split(",")

    entities = []
    for sensor_type in monitored_conditions:
        entities.append(
            OpenWeatherMapSensor(
                entity_name,
                sensor_type.strip(),
                weather_coordinator,
                forecast_coordinator,
            )
        )

    async_add_entities(entities, True)


class OpenWeatherMapSensor(Entity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(
        self,
        name,
        sensor_type,
        weather_coordinator: WeatherUpdateCoordinator,
        forecast_coordinator: ForecastUpdateCoordinator,
    ):
        """Initialize the sensor."""
        self._name = name
        self._sensor_name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._attr_key = SENSOR_TYPES[sensor_type][2]
        self._weather_coordinator = weather_coordinator
        self._forecast_coordinator = forecast_coordinator

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._weather_coordinator.data[self._attr_key]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            self._weather_coordinator.last_update_success
            and self._forecast_coordinator.last_update_success
        )

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self._weather_coordinator.async_add_listener(self.async_write_ha_state)
        self._forecast_coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self._weather_coordinator.async_remove_listener(self.async_write_ha_state)
        self._forecast_coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self):
        """Get the latest data from OWM and updates the states."""
        await self._weather_coordinator.async_request_refresh()
        await self._forecast_coordinator.async_request_refresh()

    # def update_old(self):
    #     """Get the latest data from OWM and updates the states."""
    #     try:
    #         self.owa_client.update()
    #     except APICallError:
    #         _LOGGER.error("Error when calling API to update data")
    #         return
    #
    #     data = self.owa_client.data
    #     forecast_data = self.owa_client.forecast_data
    #
    #     if data is None:
    #         return
    #
    #     try:
    #         if self.type == "weather":
    #             self._state = data.get_detailed_status()
    #         elif self.type == "temperature":
    #             if self.temp_unit == TEMP_CELSIUS:
    #                 self._state = round(data.get_temperature("celsius")["temp"], 1)
    #             elif self.temp_unit == TEMP_FAHRENHEIT:
    #                 self._state = round(data.get_temperature("fahrenheit")["temp"], 1)
    #             else:
    #                 self._state = round(data.get_temperature()["temp"], 1)
    #         elif self.type == "wind_speed":
    #             self._state = round(data.get_wind()["speed"], 1)
    #         elif self.type == "wind_bearing":
    #             self._state = round(data.get_wind()["deg"], 1)
    #         elif self.type == "humidity":
    #             self._state = round(data.get_humidity(), 1)
    #         elif self.type == "pressure":
    #             self._state = round(data.get_pressure()["press"], 0)
    #         elif self.type == "clouds":
    #             self._state = data.get_clouds()
    #         elif self.type == "rain":
    #             rain = data.get_rain()
    #             if "3h" in rain:
    #                 self._state = round(rain["3h"], 0)
    #                 self._unit_of_measurement = "mm"
    #             else:
    #                 self._state = "not raining"
    #                 self._unit_of_measurement = ""
    #         elif self.type == "snow":
    #             if data.get_snow():
    #                 self._state = round(data.get_snow(), 0)
    #                 self._unit_of_measurement = "mm"
    #             else:
    #                 self._state = "not snowing"
    #                 self._unit_of_measurement = ""
    #         elif self.type == "forecast":
    #             if forecast_data is None:
    #                 return
    #             self._state = forecast_data.get_weathers()[0].get_detailed_status()
    #         elif self.type == "weather_code":
    #             self._state = data.get_weather_code()
    #     except KeyError:
    #         self._state = None
    #         _LOGGER.warning("Condition is currently not available: %s", self.type)
