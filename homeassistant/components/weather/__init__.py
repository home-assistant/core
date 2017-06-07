"""
Weather component that handles meteorological data for your location.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/weather/
"""
import asyncio
import logging
from numbers import Number

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []
DOMAIN = 'weather'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_CONDITION_CLASS = 'condition_class'
ATTR_FORECAST = 'forecast'
ATTR_FORECAST_TEMP = 'temperature'
ATTR_FORECAST_TIME = 'datetime'
ATTR_WEATHER_ATTRIBUTION = 'attribution'
ATTR_WEATHER_HUMIDITY = 'humidity'
ATTR_WEATHER_OZONE = 'ozone'
ATTR_WEATHER_PRESSURE = 'pressure'
ATTR_WEATHER_TEMPERATURE = 'temperature'
ATTR_WEATHER_VISIBILITY = 'visibility'
ATTR_WEATHER_WIND_BEARING = 'wind_bearing'
ATTR_WEATHER_WIND_SPEED = 'wind_speed'


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the weather component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    yield from component.async_setup(config)
    return True


# pylint: disable=no-member, no-self-use
class WeatherEntity(Entity):
    """ABC for weather data."""

    @property
    def temperature(self):
        """Return the platform temperature."""
        raise NotImplementedError()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        raise NotImplementedError()

    @property
    def pressure(self):
        """Return the pressure."""
        return None

    @property
    def humidity(self):
        """Return the humidity."""
        raise NotImplementedError()

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return None

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return None

    @property
    def ozone(self):
        """Return the ozone level."""
        return None

    @property
    def attribution(self):
        """Return the attribution."""
        return None

    @property
    def visibility(self):
        """Return the visibility."""
        return None

    @property
    def forecast(self):
        """Return the forecast."""
        return None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {
            ATTR_WEATHER_TEMPERATURE: self._temp_for_display(self.temperature),
            ATTR_WEATHER_HUMIDITY: self.humidity,
        }

        ozone = self.ozone
        if ozone is not None:
            data[ATTR_WEATHER_OZONE] = ozone

        pressure = self.pressure
        if pressure is not None:
            data[ATTR_WEATHER_PRESSURE] = pressure

        wind_bearing = self.wind_bearing
        if wind_bearing is not None:
            data[ATTR_WEATHER_WIND_BEARING] = wind_bearing

        wind_speed = self.wind_speed
        if wind_speed is not None:
            data[ATTR_WEATHER_WIND_SPEED] = wind_speed

        visibility = self.visibility
        if visibility is not None:
            data[ATTR_WEATHER_VISIBILITY] = visibility

        attribution = self.attribution
        if attribution is not None:
            data[ATTR_WEATHER_ATTRIBUTION] = attribution

        if self.forecast is not None:
            forecast = []
            for forecast_entry in self.forecast:
                forecast_entry = dict(forecast_entry)
                forecast_entry[ATTR_FORECAST_TEMP] = self._temp_for_display(
                    forecast_entry[ATTR_FORECAST_TEMP])
                forecast.append(forecast_entry)

            data[ATTR_FORECAST] = forecast

        return data

    @property
    def state(self):
        """Return the current state."""
        return self.condition

    @property
    def condition(self):
        """Return the current condition."""
        raise NotImplementedError()

    def _temp_for_display(self, temp):
        """Convert temperature into preferred units for display purposes."""
        unit = self.temperature_unit
        hass_unit = self.hass.config.units.temperature_unit

        if (temp is None or not isinstance(temp, Number) or
                unit == hass_unit):
            return temp

        value = convert_temperature(temp, unit, hass_unit)

        if hass_unit == TEMP_CELSIUS:
            return round(value, 1)
        else:
            # Users of fahrenheit generally expect integer units.
            return round(value)
