"""Tests Starlink integration init/unload."""

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import grpc
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)
from starlink_grpc import GrpcError

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonArrayType

from . import setup_integration


class _FakeRpcError(grpc.RpcError, grpc.Call):
    """A concrete grpc.Call double carrying a specific status code."""

    def __init__(self, code: grpc.StatusCode) -> None:
        """Set up the fake error with the given status code."""
        self._code = code

    def code(self) -> grpc.StatusCode:
        """Return the configured status code."""
        return self._code

    def details(self) -> str:
        """Return fake details."""
        return "fake grpc error for tests"

    def cancel(self) -> bool:
        """Return that cancellation is a no-op for this fake."""
        return False

    def is_active(self) -> bool:
        """Return that this fake call is not active."""
        return False

    def time_remaining(self) -> float | None:
        """Return that this fake call has no deadline."""
        return None

    def add_callback(self, callback: Callable[[], None]) -> bool:
        """Return that callback registration is a no-op for this fake."""
        return False

    def initial_metadata(self) -> tuple:
        """Return empty initial metadata."""
        return ()

    def trailing_metadata(self) -> tuple:
        """Return empty trailing metadata."""
        return ()


def _raise_grpc_error(code: grpc.StatusCode):
    """Build a side_effect that raises GrpcError chained to a given status code.

    Mirrors how starlink_grpc itself raises: `raise GrpcError(e) from e`, so
    exc.__cause__ is a real grpc.Call with a real .code().
    """

    def _raiser(*args, **kwargs):
        cause = _FakeRpcError(code)
        raise GrpcError(cause) from cause

    return _raiser


UNIMPLEMENTED = _raise_grpc_error(grpc.StatusCode.UNIMPLEMENTED)
UNAVAILABLE = _raise_grpc_error(grpc.StatusCode.UNAVAILABLE)


def _entity_state(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity's state, asserting it's registered."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _status_with_uptime(status_data: JsonArrayType, uptime: int) -> JsonArrayType:
    """Return status data with the given uptime."""
    status = deepcopy(status_data)
    status[0]["uptime"] = uptime
    return status


async def test_successful_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test configuring Starlink."""
    assert init_integration.runtime_data
    assert init_integration.runtime_data.data
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "location_side_effect",
    [None, UNIMPLEMENTED],
    ids=["location_available", "location_unimplemented"],
)
@pytest.mark.parametrize(
    "sleep_side_effect",
    [None, UNIMPLEMENTED],
    ids=["sleep_available", "sleep_unimplemented"],
)
async def test_setup_with_unimplemented_location_or_sleep(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_location_data: MagicMock,
    mock_sleep_config: MagicMock,
    location_side_effect: Callable | None,
    sleep_side_effect: Callable | None,
) -> None:
    """Test that setup still succeeds when the dish reports GetLocation/DishGetConfig as Unimplemented."""
    mock_location_data.side_effect = location_side_effect
    mock_sleep_config.side_effect = sleep_side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data
    assert mock_config_entry.runtime_data.data


async def test_unimplemented_rpcs_are_not_retried_on_later_polls(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_location_data: MagicMock,
    mock_sleep_config: MagicMock,
    mock_status_data: MagicMock,
) -> None:
    """Test location_data/get_sleep_config aren't called again once found Unimplemented."""
    mock_location_data.side_effect = UNIMPLEMENTED
    mock_sleep_config.side_effect = UNIMPLEMENTED

    await setup_integration(hass, mock_config_entry)

    assert mock_location_data.call_count == 1
    assert mock_sleep_config.call_count == 1
    assert mock_status_data.call_count == 1

    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_location_data.call_count == 1
    assert mock_sleep_config.call_count == 1
    assert mock_status_data.call_count == 3


async def test_sleep_entities_not_created_when_sleep_unimplemented(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sleep_config: MagicMock,
) -> None:
    """Test sleep-related entities aren't created at all when unsupported."""
    mock_sleep_config.side_effect = UNIMPLEMENTED

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.data.sleep is None
    assert hass.states.get("switch.starlink_sleep_schedule") is None
    assert hass.states.get("time.starlink_sleep_start") is None
    assert hass.states.get("time.starlink_sleep_end") is None
    # A switch unrelated to sleep config must stay unaffected.
    assert _entity_state(hass, "switch.starlink_stowed") == "off"


@pytest.mark.parametrize(
    ("location_side_effect", "expect_registered"),
    [
        pytest.param(None, True, id="location_available"),
        pytest.param(UNIMPLEMENTED, False, id="location_unimplemented"),
    ],
)
async def test_device_tracker_only_created_when_location_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_location_data: MagicMock,
    location_side_effect: Callable | None,
    expect_registered: bool,
) -> None:
    """Test the device tracker is only registered when location is supported.

    device_location is disabled by default, so checking hass.states wouldn't
    distinguish "not created" from "created but disabled" - check the entity
    registry directly instead.
    """
    mock_location_data.side_effect = location_side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    entity_id = entity_registry.async_get_entity_id(
        "device_tracker",
        DOMAIN,
        f"{mock_config_entry.runtime_data.data.status['id']}_device_location",
    )
    assert (entity_id is not None) is expect_registered


async def test_device_tracker_unavailable_when_location_becomes_unsupported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_location_data: MagicMock,
) -> None:
    """Test the tracker goes unavailable if a later poll finds location unsupported.

    Regression guard: location can go from supported to None mid-session (the
    entity was already registered on a prior successful poll), and latitude_fn
    etc. returning None must not be mistaken for a real "unknown location" -
    the entity should report unavailable, not a stale/blank location.
    """
    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "device_tracker",
        DOMAIN,
        f"{mock_config_entry.runtime_data.data.status['id']}_device_location",
    )
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()

    # Enabling a previously-disabled entity schedules its own debounced
    # reload (RELOAD_AFTER_UPDATE_DELAY); let it fire instead of racing
    # it with a manual reload, which would leave the timer lingering.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _entity_state(hass, entity_id) != "unavailable"

    mock_location_data.side_effect = UNIMPLEMENTED
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.last_update_success is True
    assert mock_config_entry.runtime_data.data.location is None
    assert _entity_state(hass, entity_id) == "unavailable"


async def test_sleep_switch_reports_real_off_when_supported(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the sleep switch reports a real 'off', not unavailable, when supported."""
    # sleep_data_success.json's third element (enabled) is false.
    assert _entity_state(hass, "switch.starlink_sleep_schedule") == "off"


async def test_switches_unavailable_when_coordinator_refresh_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_status_data: MagicMock,
) -> None:
    """Test switches go unavailable when the coordinator itself fails to refresh.

    Regression guard: the per-switch available_fn must not bypass
    CoordinatorEntity's own availability (coordinator.last_update_success).
    """
    assert _entity_state(hass, "switch.starlink_stowed") == "off"
    assert _entity_state(hass, "switch.starlink_sleep_schedule") in ("on", "off")

    mock_status_data.side_effect = UNAVAILABLE
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert init_integration.runtime_data.last_update_success is False
    assert _entity_state(hass, "switch.starlink_stowed") == "unavailable"
    assert _entity_state(hass, "switch.starlink_sleep_schedule") == "unavailable"


@pytest.mark.parametrize(
    ("location_side_effect", "sleep_side_effect"),
    [
        pytest.param(UNAVAILABLE, None, id="location_unavailable"),
        pytest.param(None, UNAVAILABLE, id="sleep_unavailable"),
        pytest.param(UNAVAILABLE, UNAVAILABLE, id="both_unavailable"),
    ],
)
async def test_setup_retries_on_other_grpc_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_location_data: MagicMock,
    mock_sleep_config: MagicMock,
    location_side_effect: Callable | None,
    sleep_side_effect: Callable | None,
) -> None:
    """Test that non-Unimplemented gRPC errors still fail setup as before.

    Only Unimplemented should be swallowed. A real communication failure
    (e.g. Unavailable) must still surface as a failed/retried setup instead
    of being silently treated as "no data".
    """
    mock_location_data.side_effect = location_side_effect
    mock_sleep_config.side_effect = sleep_side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("method", "arg"),
    [
        ("async_set_sleep_schedule_enabled", True),
        ("async_set_sleep_start", 60),
        ("async_set_sleep_duration", 120),
    ],
)
async def test_sleep_setters_raise_when_sleep_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sleep_config: MagicMock,
    method: str,
    arg: bool | int,
) -> None:
    """Test the sleep setters refuse to write when sleep config is unsupported."""
    mock_sleep_config.side_effect = UNIMPLEMENTED

    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.starlink.coordinator.set_sleep_config"
        ) as set_sleep_mock,
        pytest.raises(HomeAssistantError, match="not supported"),
    ):
        await getattr(mock_config_entry.runtime_data, method)(arg)

    set_sleep_mock.assert_not_called()


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test removing Starlink."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_restore_cache_with_accumulation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Starlink accumulation."""
    entity_id = "sensor.starlink_energy"

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    entity_id,
                    "",
                ),
                {
                    "native_value": 1,
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data
    assert mock_config_entry.runtime_data.data

    assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

    with patch.object(
        mock_config_entry.runtime_data, "always_update", return_value=True
    ):
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == str(1 + 0.01572462736977)


async def test_last_restart_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_status_data: MagicMock,
    status_data: JsonArrayType,
) -> None:
    """Test Starlink last restart state."""
    entity_id = "sensor.starlink_last_restart"
    utc_now = datetime.fromisoformat("2025-10-22T13:31:29+00:00")

    with freeze_time(utc_now):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

    with patch.object(
        mock_config_entry.runtime_data, "always_update", return_value=True
    ):
        mock_status_data.return_value = _status_with_uptime(status_data, 804144)

        with freeze_time(utc_now + timedelta(seconds=5)):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
            await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

        mock_status_data.return_value = _status_with_uptime(status_data, 804134)

        with freeze_time(utc_now + timedelta(seconds=10)):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
            await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

        mock_status_data.return_value = _status_with_uptime(status_data, 100)

        with freeze_time(utc_now + timedelta(seconds=15)):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
            await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(entity_id).state == "2025-10-22T13:30:04+00:00"
