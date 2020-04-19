"""Support for retrieving meteorological data from FMI (Finnish Meteorological Institute)."""

import logging

from dateutil import tz

# Import homeassistant platform dependencies
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    WeatherEntity,
)

from . import ATTRIBUTION, DOMAIN, get_weather_symbol

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FMI weather platform."""
    if discovery_info is None:
        return

    add_entities([FMIWeather(DOMAIN, hass.data[DOMAIN]["fmi_object"])], True)


class FMIWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, domain, fmi_weather):
        """Initialize FMI weather object."""
        self._fmi = fmi_weather

        if fmi_weather is None:
            self._name = domain
        else:
            self._name = fmi_weather.name

    @property
    def available(self):
        """Return if weather data is available from FMI."""
        if self._fmi is None:
            return False

        return self._fmi.current is not None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature(self):
        """Return the temperature."""
        if self._fmi is None:
            return None

        return self._fmi.current.data.temperature.value

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._fmi is None:
            return None

        return self._fmi.current.data.temperature.unit

    @property
    def humidity(self):
        """Return the humidity."""
        if self._fmi is None:
            return None

        return self._fmi.current.data.humidity.value

    @property
    def precipitation(self):
        """Return the humidity."""
        if self._fmi is None:
            return None

        return self._fmi.current.data.precipitation_amount.value

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self._fmi is None:
            return None

        return round(
            self._fmi.current.data.wind_speed.value * 3.6, 1
        )  # Convert m/s to km/hr

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        if self._fmi is None:
            return None

        return self._fmi.current.data.wind_direction.value

    @property
    def pressure(self):
        """Return the pressure."""
        if self._fmi is None:
            return None

        return self._fmi.current.data.pressure.value

    @property
    def condition(self):
        """Return the condition."""
        if self._fmi is None:
            return None

        return get_weather_symbol(self._fmi.current.data.symbol.value, self._fmi.hass)

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._fmi is None:
            return None

        if self._fmi.hourly is None:
            return None

        data = None

        data = [
            {
                ATTR_FORECAST_TIME: forecast.time.astimezone(tz.tzlocal()),
                ATTR_FORECAST_CONDITION: get_weather_symbol(forecast.symbol.value),
                ATTR_FORECAST_TEMP: forecast.temperature.value,
                ATTR_FORECAST_PRECIPITATION: forecast.precipitation_amount.value,
                ATTR_FORECAST_WIND_SPEED: forecast.wind_speed.value,
                ATTR_FORECAST_WIND_BEARING: forecast.wind_direction.value,
                ATTR_WEATHER_PRESSURE: forecast.pressure.value,
                ATTR_WEATHER_HUMIDITY: forecast.humidity.value,
            }
            for forecast in self._fmi.hourly.forecasts
        ]

        # if the first few precipitation values in forecast is 0, no need to include them
        # in UI
        include_precipitation = False
        len_check = 5 if len(data) > 5 else len(data)
        for _, dt_w in zip(range(len_check), data):
            if dt_w[ATTR_FORECAST_PRECIPITATION] > 0.0:
                include_precipitation = True
                break

        if include_precipitation is False:
            for _, dt_w in zip(range(len_check), data):
                del dt_w[ATTR_FORECAST_PRECIPITATION]

        return data

    def update(self):
        """Get the latest data from FMI."""
        if self._fmi is None:
            return None

        self._fmi.update()
