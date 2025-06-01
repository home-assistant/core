"""Test Volvo coordinator."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoApiException, VolvoAuthException

from homeassistant.components.volvo.coordinator import VolvoDataCoordinator
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_coordinator_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_config_entry: MockConfigEntry,
    mock_api: VolvoCarsApi,
) -> None:
    """Test coordinator update with errors."""
    assert await setup_integration()

    sensor_id = "sensor.volvo_xc40_odometer"
    coordinator: VolvoDataCoordinator = mock_config_entry.runtime_data
    interval = timedelta(seconds=coordinator.update_interval.total_seconds() + 5)
    original_value = coordinator._refresh_conditions["odometer"][0].return_value
    mock_method: AsyncMock = mock_api.async_get_odometer

    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    _configure_mock(mock_method, return_value=None, side_effect=VolvoApiException())
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == STATE_UNAVAILABLE

    _configure_mock(mock_method, return_value=original_value, side_effect=None)
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    _configure_mock(mock_method, return_value=None, side_effect=VolvoAuthException())
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == STATE_UNAVAILABLE

    _configure_mock(mock_method, return_value=original_value, side_effect=None)
    # Explicitly refresh to recover from auth failure
    await coordinator.async_refresh()
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    _configure_mock(mock_method, return_value=None, side_effect=Exception())
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == STATE_UNAVAILABLE

    _configure_mock(mock_method, return_value=original_value, side_effect=None)
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == "30000"


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_update_coordinator_all_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test API returning error for all calls during coordinator update."""
    assert await setup_integration()

    _mock_api_failure(mock_api)
    freezer.tick(timedelta(seconds=135))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for state in hass.states.async_all():
        assert state.state == STATE_UNAVAILABLE


async def test_coordinator_setup_no_vehicle(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test no vehicle during coordinator setup."""
    sensor_id = "sensor.volvo_xc40_odometer"
    mock_method: AsyncMock = mock_api.async_get_vehicle_details

    _configure_mock(mock_method, return_value=None, side_effect=None)
    assert not await setup_integration()

    state = hass.states.get(sensor_id)
    assert state is None


async def test_coordinator_setup_auth_failure(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test auth failure during coordinator setup."""
    sensor_id = "sensor.volvo_xc40_odometer"
    mock_method: AsyncMock = mock_api.async_get_vehicle_details

    _configure_mock(mock_method, return_value=None, side_effect=VolvoAuthException())
    assert not await setup_integration()

    state = hass.states.get(sensor_id)
    assert state is None


def _configure_mock(mock: AsyncMock, *, return_value: Any, side_effect: Any) -> None:
    mock.reset_mock()
    mock.side_effect = side_effect
    mock.return_value = return_value


def _mock_api_failure(mock_api: VolvoCarsApi) -> AsyncMock:
    """Mock the Volvo API so that it raises an exception for all calls."""

    mock_api.async_get_brakes_status.side_effect = VolvoApiException()
    mock_api.async_get_command_accessibility.side_effect = VolvoApiException()
    mock_api.async_get_commands.side_effect = VolvoApiException()
    mock_api.async_get_diagnostics.side_effect = VolvoApiException()
    mock_api.async_get_doors_status.side_effect = VolvoApiException()
    mock_api.async_get_engine_status.side_effect = VolvoApiException()
    mock_api.async_get_engine_warnings.side_effect = VolvoApiException()
    mock_api.async_get_fuel_status.side_effect = VolvoApiException()
    mock_api.async_get_location.side_effect = VolvoApiException()
    mock_api.async_get_odometer.side_effect = VolvoApiException()
    mock_api.async_get_recharge_status.side_effect = VolvoApiException()
    mock_api.async_get_statistics.side_effect = VolvoApiException()
    mock_api.async_get_tyre_states.side_effect = VolvoApiException()
    mock_api.async_get_warnings.side_effect = VolvoApiException()
    mock_api.async_get_window_states.side_effect = VolvoApiException()

    return mock_api
