"""
Demo platform that offers fake meteorological data.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from datetime import datetime, timedelta

from homeassistant.components.weather import (
    WeatherEntity, ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT)

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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo weather."""
    add_devices([
        DemoWeather('South', 'Sunshine', 21, 92, 1099, 0.5, TEMP_CELSIUS,
                    [22, 19, 15, 12, 14, 18, 21]),
        DemoWeather('North', 'Shower rain', -12, 54, 987, 4.8, TEMP_FAHRENHEIT,
                    [-10, -13, -18, -23, -19, -14, -9])
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
                ATTR_FORECAST_TEMP: entry
            }
            reftime = reftime + timedelta(hours=4)
            forecast_data.append(data_dict)

        return forecast_data
