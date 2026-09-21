"""Test for the weather entity of the IRM KMI integration."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .const import WEATHER_ENTITY_ID

from tests.common import MockConfigEntry, snapshot_platform


async def _get_forecast(
    hass: HomeAssistant, forecast_type: str
) -> list[dict[str, Any]]:
    """Return the forecast from weather.get_forecasts."""
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            ATTR_ENTITY_ID: WEATHER_ENTITY_ID,
            "type": forecast_type,
        },
        blocking=True,
        return_response=True,
    )
    return response[WEATHER_ENTITY_ID]["forecast"]


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize("forecast_fixture", ["forecast_nl.json"])
@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_weather_nl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test weather with forecast from the Netherland."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize("forecast_fixture", ["forecast_nl.json"])
@pytest.mark.parametrize(
    "forecast_type",
    ["daily", "hourly"],
)
@pytest.mark.freeze_time("2025-09-22T15:30:00+01:00")
async def test_forecast_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    forecast_type: str,
) -> None:
    """Test multiple forecast."""
    await setup_integration(hass, mock_config_entry)

    assert await _get_forecast(hass, forecast_type) == snapshot


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize("forecast_fixture", ["high_low_temp.json"])
@pytest.mark.freeze_time("2024-01-21T14:15:00+01:00")
async def test_daily_forecast_night_low_above_day_high(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a night low above the day high is swapped into the first day."""
    # Test case for https://github.com/jdejaegh/irm-kmi-ha/issues/8
    await setup_integration(hass, mock_config_entry)

    assert [
        (forecast["temperature"], forecast["templow"])
        for forecast in await _get_forecast(hass, "daily")
    ] == [
        (4.0, 3.0),
        (10.0, 1.0),
        (8.0, 3.0),
        (12.0, 10.0),
        (8.0, 2.0),
        (8.0, 6.0),
        (6.0, -2.0),
    ]
