"""Test Volvo coordinator."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
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
from homeassistant.components.volvo.coordinator import (
    FAST_INTERVAL,
    MEDIUM_INTERVAL,
    VERY_SLOW_INTERVAL,
    VolvoConfigEntry,
    VolvoSlowIntervalCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import configure_mock

from tests.common import MockConfigEntry, async_fire_time_changed


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
        if state.domain != "button":
            assert state.state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_coordinator_location_exception(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test coordinator setup when location returns an exception."""
    configure_mock(
        mock_api.async_get_location, side_effect=VolvoAuthException(403, "Forbidden")
    )
    assert await setup_integration()

    # Verify no reauthentication flow is started
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not flows

    # Verify integration loads without location entity
    device_tracker_states = hass.states.async_all(domain_filter="device_tracker")
    assert len(device_tracker_states) == 0

    # Verify other entities still work
    sensor_id = "sensor.volvo_xc40_odometer"
    state = hass.states.get(sensor_id)
    assert state.state == "30000"


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_engine_off_triggers_location_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test that engine turning off triggers a location update."""
    # Start with engine RUNNING
    configure_mock(
        mock_api.async_get_engine_status,
        return_value={"engineStatus": VolvoCarsValueField(value="RUNNING")},
    )
    assert await setup_integration()

    location_call_count_before: int = mock_api.async_get_location.call_count

    # Engine turns off on next poll
    configure_mock(
        mock_api.async_get_engine_status,
        return_value={"engineStatus": VolvoCarsValueField(value="STOPPED")},
    )
    freezer.tick(timedelta(minutes=MEDIUM_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_api.async_get_location.call_count > location_call_count_before


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_engine_stays_running_no_extra_location(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test that engine staying RUNNING does not trigger extra location update."""
    configure_mock(
        mock_api.async_get_engine_status,
        return_value={"engineStatus": VolvoCarsValueField(value="RUNNING")},
    )
    assert await setup_integration()

    location_call_count_before: int = mock_api.async_get_location.call_count

    # Engine stays RUNNING on next poll
    freezer.tick(timedelta(minutes=MEDIUM_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_api.async_get_location.call_count == location_call_count_before


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_physical_lock_triggers_location_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test that physical lock (key fob) triggers a location update."""
    # Start with car unlocked
    doors_unlocked = await _async_get_doors_data(mock_api, "UNLOCKED")
    configure_mock(mock_api.async_get_doors_status, return_value=doors_unlocked)
    assert await setup_integration()

    location_call_count_before: int = mock_api.async_get_location.call_count

    # Car gets locked physically on next poll
    doors_locked = await _async_get_doors_data(mock_api, "LOCKED")
    configure_mock(mock_api.async_get_doors_status, return_value=doors_locked)
    freezer.tick(timedelta(minutes=FAST_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_api.async_get_location.call_count > location_call_count_before


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_physical_unlock_does_not_trigger_location_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test that unlocking does not trigger a location update."""
    assert await setup_integration()

    location_call_count_before: int = mock_api.async_get_location.call_count

    # Car gets unlocked on next poll
    doors_unlocked = await _async_get_doors_data(mock_api, "UNLOCKED")
    configure_mock(mock_api.async_get_doors_status, return_value=doors_unlocked)
    freezer.tick(timedelta(minutes=FAST_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_api.async_get_location.call_count == location_call_count_before


@pytest.mark.freeze_time("2025-05-31T10:00:00+00:00")
async def test_location_update_not_supported(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test that async_update_location is a no-op when location is unsupported."""
    configure_mock(
        mock_api.async_get_location, side_effect=VolvoAuthException(403, "Forbidden")
    )
    assert await setup_integration()
    mock_api.async_get_location.reset_mock()

    configure_mock(
        mock_api.async_get_engine_status,
        return_value={"engineStatus": VolvoCarsValueField(value="RUNNING")},
    )

    entry: VolvoConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    for c in entry.runtime_data.interval_coordinators:
        if isinstance(c, VolvoSlowIntervalCoordinator):
            await c.async_update_location()
            break

    mock_api.async_get_location.assert_not_called()


async def test_coordinator_setup_auth_exception(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_config_entry: MockConfigEntry,
    mock_api: VolvoCarsApi,
) -> None:
    """Test coordinator setup when determine API calls raises auth exception."""
    configure_mock(
        mock_api.async_get_energy_capabilities,
        side_effect=VolvoAuthException(401, "Unauthorized"),
    )

    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_setup_not_ready_exception(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_config_entry: MockConfigEntry,
    mock_api: VolvoCarsApi,
) -> None:
    """Test coordinator setup when determine API calls raises API exception."""
    configure_mock(
        mock_api.async_get_energy_capabilities, side_effect=VolvoApiException
    )

    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        VolvoApiException("Location failed"),
        VolvoAuthException(401, "Unauthorized"),
    ],
)
async def test_update_location_exception_logs_debug(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
    caplog: pytest.LogCaptureFixture,
    exception: VolvoApiException | VolvoAuthException,
) -> None:
    """Test async_update_location logs debug when location call fails."""
    assert await setup_integration()

    entry: VolvoConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    slow_coordinator = next(
        c
        for c in entry.runtime_data.interval_coordinators
        if isinstance(c, VolvoSlowIntervalCoordinator)
    )

    configure_mock(mock_api.async_get_location, side_effect=exception)

    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.volvo.coordinator"
    ):
        await slow_coordinator.async_update_location()

    assert "Location update failed" in caplog.text


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


async def _async_get_doors_data(
    mock_api: VolvoCarsApi, lock_value: str
) -> dict[str, VolvoCarsValueField]:
    """Build doors data with a specific centralLock value."""
    # Reuse the structure from the original mock but override centralLock
    original = mock_api.async_get_doors_status.return_value
    result = dict(original)
    result["centralLock"] = VolvoCarsValueField(value=lock_value)
    return result
