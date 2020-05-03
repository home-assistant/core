"""Tests for the NWS weather component."""
from datetime import timedelta

import aiohttp
import pytest

from homeassistant.components import nws
from homeassistant.components.weather import ATTR_FORECAST
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.nws.const import (
    EXPECTED_FORECAST_IMPERIAL,
    EXPECTED_FORECAST_METRIC,
    EXPECTED_OBSERVATION_IMPERIAL,
    EXPECTED_OBSERVATION_METRIC,
    NONE_FORECAST,
    NONE_OBSERVATION,
    NWS_CONFIG,
)


@pytest.mark.parametrize(
    "units,result_observation,result_forecast",
    [
        (IMPERIAL_SYSTEM, EXPECTED_OBSERVATION_IMPERIAL, EXPECTED_FORECAST_IMPERIAL),
        (METRIC_SYSTEM, EXPECTED_OBSERVATION_METRIC, EXPECTED_FORECAST_METRIC),
    ],
)
async def test_imperial_metric(
    hass, units, result_observation, result_forecast, mock_simple_nws
):
    """Test with imperial and metric units."""
    hass.config.units = units
    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_hourly")

    assert state
    assert state.state == "sunny"

    data = state.attributes
    for key, value in result_observation.items():
        assert data.get(key) == value

    forecast = data.get(ATTR_FORECAST)
    for key, value in result_forecast.items():
        assert forecast[0].get(key) == value

    state = hass.states.get("weather.abc_daynight")

    assert state
    assert state.state == "sunny"

    data = state.attributes
    for key, value in result_observation.items():
        assert data.get(key) == value

    forecast = data.get(ATTR_FORECAST)
    for key, value in result_forecast.items():
        assert forecast[0].get(key) == value


async def test_none_values(hass, mock_simple_nws):
    """Test with none values in observation and forecast dicts."""
    instance = mock_simple_nws.return_value
    instance.observation = NONE_OBSERVATION
    instance.forecast = NONE_FORECAST

    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_daynight")
    assert state.state == "unknown"
    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None

    forecast = data.get(ATTR_FORECAST)
    for key in EXPECTED_FORECAST_IMPERIAL:
        assert forecast[0].get(key) is None


async def test_none(hass, mock_simple_nws):
    """Test with None as observation and forecast."""
    instance = mock_simple_nws.return_value
    instance.observation = None
    instance.forecast = None

    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == "unknown"

    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None

    forecast = data.get(ATTR_FORECAST)
    assert forecast is None


async def test_error_station(hass, mock_simple_nws):
    """Test error in setting station."""

    instance = mock_simple_nws.return_value
    instance.set_station.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.abc_hourly") is None
    assert hass.states.get("weather.abc_daynight") is None


async def test_error_observation(hass, mock_simple_nws):
    """Test error during update observation."""
    instance = mock_simple_nws.return_value
    instance.update_observation.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance.update_observation.assert_called_once()

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == "unavailable"

    state = hass.states.get("weather.abc_hourly")
    assert state
    assert state.state == "unavailable"

    instance.update_observation.side_effect = None

    future_time = dt_util.utcnow() + timedelta(minutes=15)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()

    assert instance.update_observation.call_count == 2

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == "sunny"

    state = hass.states.get("weather.abc_hourly")
    assert state
    assert state.state == "sunny"


async def test_error_forecast(hass, mock_simple_nws):
    """Test error during update forecast."""
    instance = mock_simple_nws.return_value
    instance.update_forecast.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance.update_forecast.assert_called_once()

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == "unavailable"

    instance.update_forecast.side_effect = None

    future_time = dt_util.utcnow() + timedelta(minutes=15)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()

    assert instance.update_forecast.call_count == 2

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == "sunny"


async def test_error_forecast_hourly(hass, mock_simple_nws):
    """Test error during update forecast hourly."""
    instance = mock_simple_nws.return_value
    instance.update_forecast_hourly.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(domain=nws.DOMAIN, data=NWS_CONFIG,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_hourly")
    assert state
    assert state.state == "unavailable"

    instance.update_forecast_hourly.assert_called_once()

    instance.update_forecast_hourly.side_effect = None

    future_time = dt_util.utcnow() + timedelta(minutes=15)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()

    assert instance.update_forecast_hourly.call_count == 2

    state = hass.states.get("weather.abc_hourly")
    assert state
    assert state.state == "sunny"
