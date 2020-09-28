"""Tests for the NWS weather component."""
from datetime import timedelta

import aiohttp
import pytest

from homeassistant.components import nws
from homeassistant.components.weather import ATTR_CONDITION_SUNNY, ATTR_FORECAST
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.async_mock import patch
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
    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_hourly")

    assert state
    assert state.state == ATTR_CONDITION_SUNNY

    data = state.attributes
    for key, value in result_observation.items():
        assert data.get(key) == value

    forecast = data.get(ATTR_FORECAST)
    for key, value in result_forecast.items():
        assert forecast[0].get(key) == value

    state = hass.states.get("weather.abc_daynight")

    assert state
    assert state.state == ATTR_CONDITION_SUNNY

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

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_daynight")
    assert state.state == STATE_UNKNOWN
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

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == STATE_UNKNOWN

    data = state.attributes
    for key in EXPECTED_OBSERVATION_IMPERIAL:
        assert data.get(key) is None

    forecast = data.get(ATTR_FORECAST)
    assert forecast is None


async def test_error_station(hass, mock_simple_nws):
    """Test error in setting station."""

    instance = mock_simple_nws.return_value
    instance.set_station.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.abc_hourly") is None
    assert hass.states.get("weather.abc_daynight") is None


async def test_entity_refresh(hass, mock_simple_nws):
    """Test manual refresh."""
    instance = mock_simple_nws.return_value

    await async_setup_component(hass, "homeassistant", {})

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    instance.update_observation.assert_called_once()
    instance.update_forecast.assert_called_once()
    instance.update_forecast_hourly.assert_called_once()

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "weather.abc_daynight"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert instance.update_observation.call_count == 2
    assert instance.update_forecast.call_count == 2
    instance.update_forecast_hourly.assert_called_once()


async def test_error_observation(hass, mock_simple_nws):
    """Test error during update observation."""
    utc_time = dt_util.utcnow()
    with patch("homeassistant.components.nws.utcnow") as mock_utc, patch(
        "homeassistant.components.nws.weather.utcnow"
    ) as mock_utc_weather:

        def increment_time(time):
            mock_utc.return_value += time
            mock_utc_weather.return_value += time
            async_fire_time_changed(hass, mock_utc.return_value)

        mock_utc.return_value = utc_time
        mock_utc_weather.return_value = utc_time
        instance = mock_simple_nws.return_value
        # first update fails
        instance.update_observation.side_effect = aiohttp.ClientError

        entry = MockConfigEntry(
            domain=nws.DOMAIN,
            data=NWS_CONFIG,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        instance.update_observation.assert_called_once()

        state = hass.states.get("weather.abc_daynight")
        assert state
        assert state.state == STATE_UNAVAILABLE

        state = hass.states.get("weather.abc_hourly")
        assert state
        assert state.state == STATE_UNAVAILABLE

        # second update happens faster and succeeds
        instance.update_observation.side_effect = None
        increment_time(timedelta(minutes=1))
        await hass.async_block_till_done()

        assert instance.update_observation.call_count == 2

        state = hass.states.get("weather.abc_daynight")
        assert state
        assert state.state == ATTR_CONDITION_SUNNY

        state = hass.states.get("weather.abc_hourly")
        assert state
        assert state.state == "sunny"

        # third udate fails, but data is cached
        instance.update_observation.side_effect = aiohttp.ClientError

        increment_time(timedelta(minutes=10))
        await hass.async_block_till_done()

        assert instance.update_observation.call_count == 3

        state = hass.states.get("weather.abc_daynight")
        assert state
        assert state.state == ATTR_CONDITION_SUNNY

        state = hass.states.get("weather.abc_hourly")
        assert state
        assert state.state == ATTR_CONDITION_SUNNY

        # after 20 minutes data caching expires, data is no longer shown
        increment_time(timedelta(minutes=10))
        await hass.async_block_till_done()

        state = hass.states.get("weather.abc_daynight")
        assert state
        assert state.state == STATE_UNAVAILABLE

        state = hass.states.get("weather.abc_hourly")
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_error_forecast(hass, mock_simple_nws):
    """Test error during update forecast."""
    instance = mock_simple_nws.return_value
    instance.update_forecast.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    instance.update_forecast.assert_called_once()

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == STATE_UNAVAILABLE

    instance.update_forecast.side_effect = None

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()

    assert instance.update_forecast.call_count == 2

    state = hass.states.get("weather.abc_daynight")
    assert state
    assert state.state == ATTR_CONDITION_SUNNY


async def test_error_forecast_hourly(hass, mock_simple_nws):
    """Test error during update forecast hourly."""
    instance = mock_simple_nws.return_value
    instance.update_forecast_hourly.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.abc_hourly")
    assert state
    assert state.state == STATE_UNAVAILABLE

    instance.update_forecast_hourly.assert_called_once()

    instance.update_forecast_hourly.side_effect = None

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()

    assert instance.update_forecast_hourly.call_count == 2

    state = hass.states.get("weather.abc_hourly")
    assert state
    assert state.state == ATTR_CONDITION_SUNNY
