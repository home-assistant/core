"""Test Meteo.lt weather entity."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

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


@pytest.mark.freeze_time("2025-09-25 9:00:00")
async def test_forecast_no_limits(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that forecast returns all available data from API without limits."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.vilnius", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    hourly_forecasts = result["weather.vilnius"]["forecast"]
    assert len(hourly_forecasts) == 9

    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.vilnius", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    daily_forecasts = result["weather.vilnius"]["forecast"]
    assert len(daily_forecasts) == 7
