"""Test Volvo coordinator."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import (
    VolvoApiException,
    VolvoAuthException,
    VolvoCarsValueField,
)

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.components.volvo.coordinator import VERY_SLOW_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import configure_mock

from tests.common import async_fire_time_changed


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_coordinator_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test coordinator update."""
    assert await setup_integration()

    sensor_id = "sensor.volvo_xc40_odometer"
    interval = timedelta(minutes=VERY_SLOW_INTERVAL)
    value = {"odometer": VolvoCarsValueField(value=30000, unit="km")}
    mock_method: AsyncMock = mock_api.async_get_odometer

    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    value["odometer"].value = 30001
    configure_mock(mock_method, return_value=value)
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == "30001"


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_coordinator_with_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test coordinator with errors."""
    assert await setup_integration()

    sensor_id = "sensor.volvo_xc40_odometer"
    interval = timedelta(minutes=VERY_SLOW_INTERVAL)
    value = {"odometer": VolvoCarsValueField(value=30000, unit="km")}
    mock_method: AsyncMock = mock_api.async_get_odometer

    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    configure_mock(mock_method, side_effect=VolvoApiException())
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == STATE_UNAVAILABLE

    configure_mock(mock_method, return_value=value)
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    configure_mock(mock_method, side_effect=Exception())
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == STATE_UNAVAILABLE

    configure_mock(mock_method, return_value=value)
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == "30000"

    configure_mock(mock_method, side_effect=VolvoAuthException())
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_method.call_count == 1
    state = hass.states.get(sensor_id)
    assert state.state == STATE_UNAVAILABLE


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
    freezer.tick(timedelta(minutes=VERY_SLOW_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for state in hass.states.async_all(domain_filter=DOMAIN):
        assert state.state == STATE_UNAVAILABLE


def _mock_api_failure(mock_api: VolvoCarsApi) -> AsyncMock:
    """Mock the Volvo API so that it raises an exception for all calls."""

    mock_api.async_get_brakes_status.side_effect = VolvoApiException()
    mock_api.async_get_command_accessibility.side_effect = VolvoApiException()
    mock_api.async_get_commands.side_effect = VolvoApiException()
    mock_api.async_get_diagnostics.side_effect = VolvoApiException()
    mock_api.async_get_doors_status.side_effect = VolvoApiException()
    mock_api.async_get_energy_capabilities.side_effect = VolvoApiException()
    mock_api.async_get_energy_state.side_effect = VolvoApiException()
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
