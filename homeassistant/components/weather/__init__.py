"""
Weather component that handles meteorological data for your location.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/weather/
"""
from datetime import timedelta
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.const import PRECISION_WHOLE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_CONDITION_CLASS = 'condition_class'
ATTR_FORECAST = 'forecast'
ATTR_FORECAST_CONDITION = 'condition'
ATTR_FORECAST_PRECIPITATION = 'precipitation'
ATTR_FORECAST_TEMP = 'temperature'
ATTR_FORECAST_TEMP_LOW = 'templow'
ATTR_FORECAST_TIME = 'datetime'
ATTR_FORECAST_WIND_BEARING = 'wind_bearing'
ATTR_FORECAST_WIND_SPEED = 'wind_speed'
ATTR_WEATHER_ATTRIBUTION = 'attribution'
ATTR_WEATHER_HUMIDITY = 'humidity'
ATTR_WEATHER_OZONE = 'ozone'
ATTR_WEATHER_PRESSURE = 'pressure'
ATTR_WEATHER_TEMPERATURE = 'temperature'
ATTR_WEATHER_VISIBILITY = 'visibility'
ATTR_WEATHER_WIND_BEARING = 'wind_bearing'
ATTR_WEATHER_WIND_SPEED = 'wind_speed'

DOMAIN = 'weather'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass, config):
    """Set up the weather component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


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
    def precision(self):
        """Return the forecast."""
        return PRECISION_TENTHS if self.temperature_unit == TEMP_CELSIUS \
            else PRECISION_WHOLE

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {
            ATTR_WEATHER_TEMPERATURE: show_temp(
                self.hass, self.temperature, self.temperature_unit,
                self.precision),
        }

        humidity = self.humidity
        if humidity is not None:
            data[ATTR_WEATHER_HUMIDITY] = round(humidity)

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
                forecast_entry[ATTR_FORECAST_TEMP] = show_temp(
                    self.hass, forecast_entry[ATTR_FORECAST_TEMP],
                    self.temperature_unit, self.precision)
                if ATTR_FORECAST_TEMP_LOW in forecast_entry:
                    forecast_entry[ATTR_FORECAST_TEMP_LOW] = show_temp(
                        self.hass, forecast_entry[ATTR_FORECAST_TEMP_LOW],
                        self.temperature_unit, self.precision)
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
