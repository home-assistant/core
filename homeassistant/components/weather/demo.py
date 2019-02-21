"""Demo platform that offers fake meteorological data."""
from datetime import datetime, timedelta

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME, WeatherEntity)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

CONDITION_CLASSES = {
    'cloudy': [],
    'fog': [],
    'hail': [],
    'lightning': [],
    'lightning-rainy': [],
    'partlycloudy': [],
    'pouring': [],
    'rainy': ['shower rain'],
    'snowy': [],
    'snowy-rainy': [],
    'sunny': ['sunshine'],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo weather."""
    add_entities([
        DemoWeather('South', 'Sunshine', 21.6414, 92, 1099, 0.5, TEMP_CELSIUS,
                    [['rainy', 1, 22, 15], ['rainy', 5, 19, 8],
                     ['cloudy', 0, 15, 9], ['sunny', 0, 12, 6],
                     ['partlycloudy', 2, 14, 7], ['rainy', 15, 18, 7],
                     ['fog', 0.2, 21, 12]]),
        DemoWeather('North', 'Shower rain', -12, 54, 987, 4.8, TEMP_FAHRENHEIT,
                    [['snowy', 2, -10, -15], ['partlycloudy', 1, -13, -14],
                     ['sunny', 0, -18, -22], ['sunny', 0.1, -23, -23],
                     ['snowy', 4, -19, -20], ['sunny', 0.3, -14, -19],
                     ['sunny', 0, -9, -12]])
    ])


class DemoWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, name, condition, temperature, humidity, pressure,
                 wind_speed, temperature_unit, forecast):
        """Initialize the Demo weather."""
        self._name = name
        self._condition = condition
        self._temperature = temperature
        self._temperature_unit = temperature_unit
        self._humidity = humidity
        self._pressure = pressure
        self._wind_speed = wind_speed
        self._forecast = forecast

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format('Demo Weather', self._name)

    @property
    def should_poll(self):
        """No polling needed for a demo weather condition."""
        return False

    @property
    def temperature(self):
        """Return the temperature."""
        return self._temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def humidity(self):
        """Return the humidity."""
        return self._humidity

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._wind_speed

    @property
    def pressure(self):
        """Return the pressure."""
        return self._pressure

    @property
    def condition(self):
        """Return the weather condition."""
        return [k for k, v in CONDITION_CLASSES.items() if
                self._condition.lower() in v][0]

    @property
    def attribution(self):
        """Return the attribution."""
        return 'Powered by Home Assistant'

    @property
    def forecast(self):
        """Return the forecast."""
        reftime = datetime.now().replace(hour=16, minute=00)

        forecast_data = []
        for entry in self._forecast:
            data_dict = {
                ATTR_FORECAST_TIME: reftime.isoformat(),
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_PRECIPITATION: entry[1],
                ATTR_FORECAST_TEMP: entry[2],
                ATTR_FORECAST_TEMP_LOW: entry[3]
            }
            reftime = reftime + timedelta(hours=4)
            forecast_data.append(data_dict)

        return forecast_data
