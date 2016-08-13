"""The tests for the Open Weather Map platform."""
import unittest
from unittest.mock import MagicMock

from homeassistant.components.sensor import openweathermap

ICONS = {
    200: 'mdi:weather-lightning-rainy',
    211: 'mdi:weather-lightning',
    300: 'mdi:weather-rainy',
    500: 'mdi:weather-rainy',
    502: 'mdi:weather-pouring',
    511: 'mdi:weather-snowy-rainy',
    600: 'mdi:weather-snowy',
    611: 'mdi:weather-snowy-rainy',
    741: 'mdi:weather-fog',
    771: 'mdi:weather-windy',
    800: 'mdi:weather-sunny',
    801: 'mdi:weather-partlycloudy',
    804: 'mdi:weather-cloudy',
    905: 'mdi:weather-windy',
    906: 'mdi:weather-hail',
    951: 'mdi:weather-sunny',
    956: 'mdi:weather-windy',
    960: 'mdi:weather-lightning',
}


class TestOpenWeatherMap(unittest.TestCase):
    """Test the Open Weather Map platform."""

    def test_weather_icons(self):
        """Test weather icons for frontend display."""
        weather_entity = openweathermap.OpenWeatherMapSensor(
            MagicMock(), "weather", None)
        for code, icon in ICONS.items():
            weather_entity._weather_code = code
            self.assertEqual(weather_entity.entity_picture, icon)
