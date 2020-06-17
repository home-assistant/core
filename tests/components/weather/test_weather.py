"""The tests for the Weather component."""
import unittest

from homeassistant.components import weather
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_WEATHER_ATTRIBUTION,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.setup import setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import get_test_home_assistant


class TestWeather(unittest.TestCase):
    """Test the Weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        assert setup_component(
            self.hass, weather.DOMAIN, {"weather": {"platform": "demo"}}
        )
        self.hass.block_till_done()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_attributes(self):
        """Test weather attributes."""
        state = self.hass.states.get("weather.demo_weather_south")
        assert state is not None

        assert state.state == "sunny"

        data = state.attributes
        assert data.get(ATTR_WEATHER_TEMPERATURE) == 21.6
        assert data.get(ATTR_WEATHER_HUMIDITY) == 92
        assert data.get(ATTR_WEATHER_PRESSURE) == 1099
        assert data.get(ATTR_WEATHER_WIND_SPEED) == 0.5
        assert data.get(ATTR_WEATHER_WIND_BEARING) is None
        assert data.get(ATTR_WEATHER_OZONE) is None
        assert data.get(ATTR_WEATHER_ATTRIBUTION) == "Powered by Home Assistant"
        assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_CONDITION) == "rainy"
        assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_PRECIPITATION) == 1
        assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_TEMP) == 22
        assert data.get(ATTR_FORECAST)[0].get(ATTR_FORECAST_TEMP_LOW) == 15
        assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_CONDITION) == "fog"
        assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_PRECIPITATION) == 0.2
        assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_TEMP) == 21
        assert data.get(ATTR_FORECAST)[6].get(ATTR_FORECAST_TEMP_LOW) == 12
        assert len(data.get(ATTR_FORECAST)) == 7

    def test_temperature_convert(self):
        """Test temperature conversion."""
        state = self.hass.states.get("weather.demo_weather_north")
        assert state is not None

        assert state.state == "rainy"

        data = state.attributes
        assert data.get(ATTR_WEATHER_TEMPERATURE) == -24
