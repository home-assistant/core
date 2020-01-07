"""Tests for the NWS weather component."""
from unittest.mock import patch

import pytest

from homeassistant.components.weather import ATTR_FORECAST
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from .helpers import setup_nws
from .helpers.pynws import (
    EXPECTED_FORECAST_IMPERIAL,
    EXPECTED_FORECAST_METRIC,
    EXPECTED_OBSERVATION_IMPERIAL,
    EXPECTED_OBSERVATION_METRIC,
    NONE_FORECAST,
    NONE_OBSERVATION,
    mock_nws,
)


@pytest.mark.parametrize(
    "units, observation_result, forecast_result",
    [
        (IMPERIAL_SYSTEM, EXPECTED_OBSERVATION_IMPERIAL, EXPECTED_FORECAST_IMPERIAL),
        (METRIC_SYSTEM, EXPECTED_OBSERVATION_METRIC, EXPECTED_FORECAST_METRIC),
    ],
)
async def test_setup_weather(hass, units, observation_result, forecast_result):
    """Test for successfully setting up the NWS integration."""
    hass.config.units = units

    MockNws = mock_nws()
    with patch(
        "homeassistant.components.nws.SimpleNWS", return_value=MockNws(),
    ), patch(
        "homeassistant.components.nws.config_flow.SimpleNWS", return_value=MockNws(),
    ):
        await setup_nws(hass)

    state = hass.states.get("weather.ABC_hourly")
    assert state.state == "sunny"

    data = state.attributes
    for key, value in observation_result.items():
        assert data.get(key) == value
    forecast = data.get(ATTR_FORECAST)
    for key, value in forecast_result.items():
        assert forecast[0].get(key) == value

    state = hass.states.get("weather.ABC_daynight")
    assert state.state == "sunny"

    data = state.attributes
    for key, value in observation_result.items():
        assert data.get(key) == value
    forecast = data.get(ATTR_FORECAST)
    for key, value in forecast_result.items():
        assert forecast[0].get(key) == value


async def test_none_values(hass):
    """Test with none values in observation and forecast."""
    MockNws = mock_nws(OBSERVATION=NONE_OBSERVATION, FORECAST=NONE_FORECAST)

    with patch(
        "homeassistant.components.nws.SimpleNWS", return_value=MockNws(),
    ), patch(
        "homeassistant.components.nws.config_flow.SimpleNWS", return_value=MockNws(),
    ):
        await setup_nws(hass)

    state = hass.states.get("weather.ABC_hourly")
    assert state
    assert state.state == "unknown"

    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None
    forecast = data.get(ATTR_FORECAST)
    for key in EXPECTED_FORECAST_IMPERIAL:
        assert forecast[0].get(key) is None


async def test_none(hass):
    """Test with none return."""
    MockNws = mock_nws(OBSERVATION=None, FORECAST=None)

    with patch(
        "homeassistant.components.nws.SimpleNWS", return_value=MockNws(),
    ), patch(
        "homeassistant.components.nws.config_flow.SimpleNWS", return_value=MockNws(),
    ):
        await setup_nws(hass)

    state = hass.states.get("weather.ABC_hourly")
    assert state
    assert state.state == "unknown"

    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None
    forecast = data.get(ATTR_FORECAST)
    assert forecast is None
