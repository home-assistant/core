"""Test for the open meteo weather entity."""

from unittest.mock import AsyncMock

from open_meteo import Forecast
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2021-11-24T03:00:00+00:00")
async def test_forecast_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_meteo: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test forecast service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: "weather.home", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot(name="forecast_daily")

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: "weather.home", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot(name="forecast_hourly")


@pytest.mark.freeze_time("2021-11-24T03:00:00+00:00")
async def test_weather_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_meteo: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the current conditions of the weather entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.home") == snapshot

    # Only the variables the entity uses are requested as current conditions
    _, _, kwargs = mock_open_meteo.forecast.mock_calls[0]
    assert sorted(kwargs["current"]) == [
        "temperature_2m",
        "weather_code",
        "wind_direction_10m",
        "wind_speed_10m",
    ]


async def test_weather_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_open_meteo: AsyncMock,
) -> None:
    """Test the weather entity when Open-Meteo returns no data sections."""
    mock_open_meteo.forecast.return_value = Forecast.from_dict(
        {
            "latitude": 52.52,
            "longitude": 13.42,
            "generationtime_ms": 0.1,
            "utc_offset_seconds": 0,
            "timezone": "GMT",
            "timezone_abbreviation": "GMT",
            "elevation": 44.8,
        }
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.home")
    assert state is not None
    assert state.state == "unknown"
    assert "temperature" not in state.attributes

    for forecast_type in ("daily", "hourly"):
        response = await hass.services.async_call(
            WEATHER_DOMAIN,
            SERVICE_GET_FORECASTS,
            {ATTR_ENTITY_ID: "weather.home", "type": forecast_type},
            blocking=True,
            return_response=True,
        )
        assert response == {"weather.home": {"forecast": []}}
