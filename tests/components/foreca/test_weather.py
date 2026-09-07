"""Test the Foreca weather platform."""

from unittest.mock import MagicMock, patch

from pyforeca import DailyForecast, HourlyForecast
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "weather.helsinki"


@pytest.mark.usefixtures("mock_foreca_client")
async def test_weather(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state of the weather entity."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_foreca_client")
@pytest.mark.parametrize("forecast_type", ["daily", "hourly"])
async def test_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    forecast_type: str,
) -> None:
    """Test the daily and hourly forecasts."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("forecast_type", "mocked_method", "undated"),
    [
        ("daily", "forecast_daily", [DailyForecast(date=None)]),
        ("hourly", "forecast_hourly", [HourlyForecast(time=None)]),
    ],
)
async def test_forecast_without_a_time_is_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
    forecast_type: str,
    mocked_method: str,
    undated: list[DailyForecast] | list[HourlyForecast],
) -> None:
    """Test an entry the API returns without a date or time is left out."""
    getattr(mock_foreca_client, mocked_method).return_value = undated
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.WEATHER]):
        await init_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert response == {ENTITY_ID: {"forecast": []}}
