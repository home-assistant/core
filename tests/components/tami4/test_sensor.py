"""Test Tami4 sensor entities."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import create_config_entry


async def test_sensors_with_valid_data(mock_api, hass: HomeAssistant) -> None:
    """Test sensors report correct values with complete API data."""

    entry = await create_config_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    uv_installed = hass.states.get("sensor.drink_water_uv_installed")
    assert uv_installed is not None
    assert uv_installed.state == "True"

    filter_installed = hass.states.get("sensor.drink_water_filter_installed")
    assert filter_installed is not None
    assert filter_installed.state == "True"

    filter_water = hass.states.get("sensor.drink_water_filter_water_passed")
    assert filter_water is not None
    assert float(filter_water.state) == 1.0


async def test_sensors_with_none_fields(
    mock_api_none_fields, hass: HomeAssistant
) -> None:
    """Test sensors handle None water quality fields gracefully.

    When the device is disconnected from the Strauss cloud, the API may
    return None for upcoming_replacement dates and milliLittersPassed.
    """

    entry = await create_config_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    uv_replacement = hass.states.get(
        "sensor.drink_water_uv_upcoming_replacement"
    )
    assert uv_replacement is not None
    assert uv_replacement.state == STATE_UNKNOWN

    filter_replacement = hass.states.get(
        "sensor.drink_water_filter_upcoming_replacement"
    )
    assert filter_replacement is not None
    assert filter_replacement.state == STATE_UNKNOWN

    filter_water = hass.states.get("sensor.drink_water_filter_water_passed")
    assert filter_water is not None
    assert float(filter_water.state) == 0.0

    uv_installed = hass.states.get("sensor.drink_water_uv_installed")
    assert uv_installed is not None
    assert uv_installed.state == "False"

    filter_installed = hass.states.get("sensor.drink_water_filter_installed")
    assert filter_installed is not None
    assert filter_installed.state == "False"
