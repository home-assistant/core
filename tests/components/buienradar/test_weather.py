"""The tests for the buienradar weather component."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import PARSE_FAILED, PARSE_SUCCEEDED, setup_integration

WEATHER_ENTITY = "weather.buienradar"


@pytest.mark.usefixtures("mock_buienradar_data")
async def test_weather(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the weather entity state."""
    await setup_integration(hass)

    assert hass.states.get(WEATHER_ENTITY) == snapshot


@pytest.mark.usefixtures("mock_buienradar_data")
async def test_forecast(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the daily forecast."""
    await setup_integration(hass)

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {ATTR_ENTITY_ID: WEATHER_ENTITY, "type": "daily"},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot


async def test_update_failure_and_recovery(
    hass: HomeAssistant,
    mock_buienradar_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity is unavailable after a failed update and recovers."""
    await setup_integration(hass)
    assert hass.states.get(WEATHER_ENTITY).state != STATE_UNAVAILABLE

    mock_buienradar_data.side_effect = None
    mock_buienradar_data.return_value = PARSE_FAILED
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(WEATHER_ENTITY).state == STATE_UNAVAILABLE

    # A failed update is retried two minutes later.
    mock_buienradar_data.return_value = PARSE_SUCCEEDED
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(WEATHER_ENTITY).state != STATE_UNAVAILABLE


async def test_failure_during_service_quiet_hour_keeps_data(
    hass: HomeAssistant,
    mock_buienradar_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed update keeps the last data while the service updates."""
    # 23:20 UTC is 00:20 CET, inside the hour buienradar.nl updates its forecast.
    freezer.move_to("2026-01-14T23:10:00+00:00")
    await setup_integration(hass)
    state = hass.states.get(WEATHER_ENTITY)
    assert state.state != STATE_UNAVAILABLE

    mock_buienradar_data.side_effect = None
    mock_buienradar_data.return_value = PARSE_FAILED
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(WEATHER_ENTITY).state == state.state
