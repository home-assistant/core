"""Support for displaying weather info from Ecobee API."""
from datetime import datetime

from homeassistant.components import ecobee
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME, ATTR_FORECAST_WIND_SPEED, WeatherEntity)
from homeassistant.const import TEMP_FAHRENHEIT

DEPENDENCIES = ['ecobee']

ATTR_FORECAST_TEMP_HIGH = 'temphigh'
ATTR_FORECAST_PRESSURE = 'pressure'
ATTR_FORECAST_VISIBILITY = 'visibility'
ATTR_FORECAST_HUMIDITY = 'humidity'

MISSING_DATA = -5002


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ecobee weather platform."""
    if discovery_info is None:
        return
    dev = list()
    data = ecobee.NETWORK
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if 'weather' in thermostat:
            dev.append(EcobeeWeather(thermostat['name'], index))

    add_entities(dev, True)


class EcobeeWeather(WeatherEntity):
    """Representation of Ecobee weather data."""

    def __init__(self, name, index):
        """Initialize the Ecobee weather platform."""
        self._name = name
        self._index = index
        self.weather = None

    def get_forecast(self, index, param):
        """Retrieve forecast parameter."""
        try:
            forecast = self.weather['forecasts'][index]
            return forecast[param]
        except (ValueError, IndexError, KeyError):
            raise ValueError

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return self.get_forecast(0, 'condition')
        except ValueError:
            return None

    @property
    def temperature(self):
        """Return the temperature."""
        try:
            return float(self.get_forecast(0, 'temperature')) / 10
        except ValueError:
            return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        try:
            return int(self.get_forecast(0, 'pressure'))
        except ValueError:
            return None

    @property
    def humidity(self):
        """Return the humidity."""
        try:
            return int(self.get_forecast(0, 'relativeHumidity'))
        except ValueError:
            return None

    @property
    def visibility(self):
        """Return the visibility."""
        try:
            return int(self.get_forecast(0, 'visibility'))
        except ValueError:
            return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        try:
            return int(self.get_forecast(0, 'windSpeed'))
        except ValueError:
            return None

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        try:
            return int(self.get_forecast(0, 'windBearing'))
        except ValueError:
            return None

    @property
    def attribution(self):
        """Return the attribution."""
        if self.weather:
            station = self.weather.get('weatherStation', "UNKNOWN")
            time = self.weather.get('timestamp', "UNKNOWN")
            return "Ecobee weather provided by {} at {}".format(station, time)
        return None

    @property
    def forecast(self):
        """Return the forecast array."""
        try:
            forecasts = []
            for day in self.weather['forecasts']:
                date_time = datetime.strptime(day['dateTime'],
                                              '%Y-%m-%d %H:%M:%S').isoformat()
                forecast = {
                    ATTR_FORECAST_TIME: date_time,
                    ATTR_FORECAST_CONDITION: day['condition'],
                    ATTR_FORECAST_TEMP: float(day['tempHigh']) / 10,
                }
                if day['tempHigh'] == MISSING_DATA:
                    break
                if day['tempLow'] != MISSING_DATA:
                    forecast[ATTR_FORECAST_TEMP_LOW] = \
                        float(day['tempLow']) / 10
                if day['pressure'] != MISSING_DATA:
                    forecast[ATTR_FORECAST_PRESSURE] = int(day['pressure'])
                if day['windSpeed'] != MISSING_DATA:
                    forecast[ATTR_FORECAST_WIND_SPEED] = int(day['windSpeed'])
                if day['visibility'] != MISSING_DATA:
                    forecast[ATTR_FORECAST_WIND_SPEED] = int(day['visibility'])
                if day['relativeHumidity'] != MISSING_DATA:
                    forecast[ATTR_FORECAST_HUMIDITY] = \
                        int(day['relativeHumidity'])
                forecasts.append(forecast)
            return forecasts
        except (ValueError, IndexError, KeyError):
            return None

    def update(self):
        """Get the latest state of the sensor."""
        data = ecobee.NETWORK
        data.update()
        thermostat = data.ecobee.get_thermostat(self._index)
        self.weather = thermostat.get('weather', None)
