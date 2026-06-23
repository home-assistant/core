"""Test Meteo.lt weather entity."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SUNNY,
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
@pytest.mark.parametrize(
    ("latitude", "longitude", "expected_condition"),
    [
        pytest.param(
            54.68705,
            25.28291,
            ATTR_CONDITION_SUNNY,
            id="sun_up",
        ),
        pytest.param(
            32.87336,
            -117.22743,
            ATTR_CONDITION_CLEAR_NIGHT,
            id="sun_down",
        ),
    ],
)
async def test_condition_clear_maps_day_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    latitude: float,
    longitude: float,
    expected_condition: str,
) -> None:
    """Test that a clear condition code maps to sunny or clear-night based on sun position."""
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.vilnius")
    assert state is not None
    assert state.state == expected_condition


@pytest.mark.freeze_time("2025-09-25 9:00:00")
async def test_forecast_hourly(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hourly forecast returns all entries with correct condition mapping."""
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
    forecasts = result["weather.vilnius"]["forecast"]

    assert len(forecasts) == 9
    assert forecasts[1]["condition"] == ATTR_CONDITION_PARTLYCLOUDY
    assert forecasts[2]["condition"] == ATTR_CONDITION_CLOUDY
    assert forecasts[3]["condition"] == ATTR_CONDITION_RAINY


@pytest.mark.freeze_time("2025-09-25 9:00:00")
async def test_forecast_daily(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test daily forecast aggregates hourly entries into per-day summaries."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.vilnius", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    forecasts = result["weather.vilnius"]["forecast"]

    assert len(forecasts) == 7

    first_day = forecasts[0]
    assert first_day["temperature"] == 13.5  # max(10.9, 12.2, 13.5)
    assert first_day["templow"] == 10.9  # min(10.9, 12.2, 13.5)
    assert first_day["precipitation"] == pytest.approx(0.1)  # sum: 0 + 0 + 0.1
    assert first_day["condition"] == ATTR_CONDITION_CLOUDY  # midday 12:00 → "cloudy"

    second_day = forecasts[1]
    assert second_day["condition"] == ATTR_CONDITION_RAINY  # 2025-09-26 → "rain"
