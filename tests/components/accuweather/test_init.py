"""Test init of AccuWeather integration."""
from datetime import timedelta
import json
from unittest.mock import patch

from accuweather import ApiError

from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.components.accuweather import init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"


async def test_config_not_ready(hass):
    """Test for setup failure if connection to AccuWeather is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data={
            "api_key": "32-character-string-1234567890qw",
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
    )

    with patch(
        "homeassistant.components.accuweather.AccuWeather._async_get_data",
        side_effect=ApiError("API Error"),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_update_interval(hass):
    """Test correct update interval."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    current = json.loads(load_fixture("accuweather/current_conditions_data.json"))
    future = utcnow() + timedelta(minutes=40)

    with patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        return_value=current,
    ) as mock_current:

        assert mock_current.call_count == 0

        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert mock_current.call_count == 1


async def test_update_interval_forecast(hass):
    """Test correct update interval when forecast is True."""
    entry = await init_integration(hass, forecast=True)

    assert entry.state is ConfigEntryState.LOADED

    current = json.loads(load_fixture("accuweather/current_conditions_data.json"))
    forecast = json.loads(load_fixture("accuweather/forecast_data.json"))
    future = utcnow() + timedelta(minutes=80)

    with patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        return_value=current,
    ) as mock_current, patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_forecast",
        return_value=forecast,
    ) as mock_forecast:

        assert mock_current.call_count == 0
        assert mock_forecast.call_count == 0

        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert mock_current.call_count == 1
        assert mock_forecast.call_count == 1
