"""Test init of AccuWeather integration."""

from unittest.mock import AsyncMock

from accuweather import ApiError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.accuweather.const import (
    DOMAIN,
    UPDATE_INTERVAL_DAILY_FORECAST,
    UPDATE_INTERVAL_OBSERVATION,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("weather.home")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "sunny"


async def test_config_not_ready(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
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

    mock_accuweather_client.async_get_current_conditions.side_effect = ApiError(
        "API Error"
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_update_interval(
    hass: HomeAssistant,
    mock_accuweather_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test correct update interval."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    assert mock_accuweather_client.async_get_current_conditions.call_count == 1
    assert mock_accuweather_client.async_get_daily_forecast.call_count == 1

    freezer.tick(UPDATE_INTERVAL_OBSERVATION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_accuweather_client.async_get_current_conditions.call_count == 2

    freezer.tick(UPDATE_INTERVAL_DAILY_FORECAST)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_accuweather_client.async_get_daily_forecast.call_count == 2


async def test_remove_ozone_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_accuweather_client: AsyncMock,
) -> None:
    """Test remove ozone sensors from registry."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "0123456-ozone-0",
        suggested_object_id="home_ozone_0d",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = entity_registry.async_get("sensor.home_ozone_0d")
    assert entry is None
