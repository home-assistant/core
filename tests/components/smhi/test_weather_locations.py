"""Weather locations test class."""

from unittest.mock import patch

import pytest

from homeassistant.components.smhi.weather_locations import SmhiWeatherLocations


@pytest.fixture
def smhi_weather_locations():
    """Fixture to create an instance of the SmhiWeatherLocations class.

    Returns:
        SmhiWeatherLocations: An instance of the SmhiWeatherLocations class.
    """
    return SmhiWeatherLocations()


@pytest.fixture
def fake_weather_locations_data():
    """Mock weather data."""
    return {
        # ... other values not used by SmhiWeatherLocations ...
        "timeSeries": [
            {
                "parameters": [
                    {"name": "t", "values": [5]},
                    {"name": "Wsymb2", "values": [1]},
                ]
                # ... more weather data ...
            }
        ]
        # ... other values not used by SmhiWeatherLocations ...
    }


def test_get_cities(smhi_weather_locations):
    """Test the get_cities function of SmhiWeatherLocations class."""
    cities = smhi_weather_locations.get_cities()
    assert isinstance(cities, list)  # Check that cities are correct type
    assert len(cities) > 0  # Check that cities are not empty


async def test_get_weather_data(smhi_weather_locations, fake_weather_locations_data):
    """Test the get_weather_data function of SmhiWeatherLocations class."""
    with patch(
        "homeassistant.components.smhi.downloader.SmhiDownloader.download_json",
        return_value=fake_weather_locations_data,
    ):
        data = await smhi_weather_locations.get_weather_data(1, 1)
        assert isinstance(data, dict)  # Check that data is correct type
        assert len(data.get("timeSeries")) > 0  # Check that data is not empty
        assert (
            len(data.get("timeSeries")[0]) > 0
        )  # Check that parameters in data is not empty


def test_get_parameter_value(smhi_weather_locations, fake_weather_locations_data):
    """Test the get_parameter_value function of SmhiWeatherLocations class."""
    temperatrure_value = smhi_weather_locations.get_parameter_value(
        fake_weather_locations_data.get("timeSeries")[0], "t"
    )
    weather_condition_value = smhi_weather_locations.get_parameter_value(
        fake_weather_locations_data.get("timeSeries")[0], "Wsymb2"
    )

    assert temperatrure_value == 5  # Check that temperature value is correct
    assert weather_condition_value == 1  # Check that weather condition value is correct


async def test_get_weather_locations(
    smhi_weather_locations, fake_weather_locations_data
):
    """Test the get_weather_locations function of SmhiWeatherLocations class."""
    with patch(
        "homeassistant.components.smhi.downloader.SmhiDownloader.download_json",
        return_value=fake_weather_locations_data,
    ):
        weather_locations = await smhi_weather_locations.get_weather_locations()
        assert isinstance(
            weather_locations, list
        )  # Check that weather_locations are correct type
        assert len(weather_locations) > 0  # Check that weather_locations are not empty


def test_get_weather_condition_icon(smhi_weather_locations):
    """Test the get_weather_condition_icon function of SmhiWeatherLocations class."""

    # Check for some of the icon indexes
    assert smhi_weather_locations.get_weather_condition_icon(1) == "SUN"
    assert smhi_weather_locations.get_weather_condition_icon(3) == "SUN"
    assert smhi_weather_locations.get_weather_condition_icon(4) == "CLOUD"
    assert smhi_weather_locations.get_weather_condition_icon(7) == "CLOUD"
    assert smhi_weather_locations.get_weather_condition_icon(8) == "RAIN"
    assert smhi_weather_locations.get_weather_condition_icon(18) == "RAIN"
    assert smhi_weather_locations.get_weather_condition_icon(21) == "RAIN"
    assert smhi_weather_locations.get_weather_condition_icon(12) == "SNOWFLAKE"
    assert smhi_weather_locations.get_weather_condition_icon(15) == "SNOWFLAKE"
    assert smhi_weather_locations.get_weather_condition_icon(23) == "SNOWFLAKE"
    assert smhi_weather_locations.get_weather_condition_icon(27) == "SNOWFLAKE"
    assert smhi_weather_locations.get_weather_condition_icon(-1) == "NULL"
    assert smhi_weather_locations.get_weather_condition_icon(28) == "NULL"
