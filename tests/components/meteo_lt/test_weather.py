"""Test Meteo.lt weather entity."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.meteo_lt.PLATFORMS", [Platform.WEATHER]):
        yield


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_weather_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test weather entity."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_forecast_daily(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test daily forecast."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            "entity_id": "weather.vilnius",
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_forecast_hourly(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test hourly forecast."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            "entity_id": "weather.vilnius",
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.freeze_time("2025-09-25 10:00:00")
async def test_forecast_with_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteo_lt_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test forecasts return None when coordinator has no data."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_forecast = mock_meteo_lt_api.get_forecast.return_value
    mock_forecast.forecast_timestamps = []

    coordinator = mock_config_entry.runtime_data

    # Should log empty data warning
    caplog.clear()
    await coordinator.async_refresh()
    assert (
        "No forecast data available for vilnius - API returned empty timestamps"
        in caplog.text
    )

    state = hass.states.get("weather.vilnius")
    assert state is not None
    assert state.state == "unavailable"
