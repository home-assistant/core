"""Weather locations test class."""

import pytest

from homeassistant.components.smhi.weather_locations import SmhiWeatherLocations


@pytest.fixture
def smhi_weather_locations():
    """Fixture to create an instance of the SmhiWeatherLocations class.

    Returns:
        SmhiWeatherLocations: An instance of the SmhiWeatherLocations class.
    """
    return SmhiWeatherLocations()


def test_get_cities(smhi_weather_locations):
    """Test the get_cities function of SmhiWeatherLocations class."""
    cities = smhi_weather_locations.get_cities()
    assert isinstance(cities, list)  # Check that cities are correct type
    assert len(cities) > 0  # Check that cities are not empty


def test_get_weather_data():
    """Test the get_weather_data function of SmhiWeatherLocations class."""


def test_get_weather_locations():
    """Test the get_weather_locations function of SmhiWeatherLocations class."""


def test_get_weather_condition_icon():
    """Test the get_weather_condition_icon function of SmhiWeatherLocations class."""
