"""Tests for the EnergyID directives coordinator."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
import datetime as dt
from functools import partial
from typing import Any, NoReturn
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, ClientResponseError
from energyid_webhooks.directives import (
    DirectiveData,
    DirectiveResource,
    DirectiveSignal,
    SignalProvider,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.energyid.const import CONF_ENABLE_DIRECTIVES, DOMAIN
from homeassistant.components.energyid.coordinator import (
    DIRECTIVE_UPDATE_INTERVAL,
    EnergyIDDirectiveCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DIRECTIVE_ID = "11111111-1111-1111-1111-111111111111"


def _directive_fixture(
    good_slots: int = 1,
) -> tuple[DirectiveResource, DirectiveData]:
    """Return a directive with 15 minute slots: good ones first, then a neutral one."""
    slot_start = dt_util.utcnow().replace(second=0, microsecond=0) - dt.timedelta(
        minutes=5
    )
    resource = DirectiveResource(
        id=DIRECTIVE_ID,
        title="Community planner",
        description="Community balance forecast",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="community",
            display_name="Energy community",
            logo_url=None,
        ),
    )
    points = [
        DirectiveSignal(
            timestamp=slot_start + dt.timedelta(minutes=15 * slot),
            signal="++",
            color="#00750e",
            raw_value=0,
        )
        for slot in range(good_slots)
    ]
    points.append(
        DirectiveSignal(
            timestamp=slot_start + dt.timedelta(minutes=15 * good_slots),
            signal="0",
            color="#EBEBEB",
            raw_value=0,
        )
    )
    schedule = DirectiveData(
        title=resource.title,
        description=resource.description,
        interval="PT15M",
        data=tuple(points),
    )
    return resource, schedule


async def _setup_with_directives(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> EnergyIDDirectiveCoordinator:
    """Set up the entry with directives enabled and return its coordinator."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry.runtime_data.directive_coordinator


async def test_directives_require_opt_in(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test EnergyID is not asked for directives until the user opts in."""
    mock_webhook_client.api_access_token = "device-token"

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.directive_coordinator
    assert coordinator.data.resources == {}
    mock_webhook_client.get_directives.assert_not_awaited()


async def test_current_and_next_signal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the coordinator derives the current signal and the next change."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    snapshot = coordinator.data.schedules[DIRECTIVE_ID]
    assert snapshot.schedule is schedule
    state = snapshot.state_at(dt_util.utcnow())
    assert state.current == schedule.data[0]
    assert state.next_change == schedule.data[1].timestamp
    assert state.next_signal == schedule.data[1]


async def _setup_single_slot_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    slot_offset: dt.timedelta,
) -> tuple[EnergyIDDirectiveCoordinator, DirectiveSignal]:
    """Set up directives with a schedule holding one slot offset from now."""
    resource, schedule = _directive_fixture()
    point = DirectiveSignal(
        timestamp=dt_util.utcnow() + slot_offset,
        signal="++",
        color="#00750e",
        raw_value=0,
    )
    shifted = DirectiveData(
        title=schedule.title,
        description=schedule.description,
        interval=schedule.interval,
        data=(point,),
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=shifted)

    coordinator = await _setup_with_directives(hass, mock_config_entry)
    return coordinator, point


async def test_schedule_starting_later_has_next_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a schedule that starts later has no current signal but a next change."""
    coordinator, point = await _setup_single_slot_schedule(
        hass, mock_config_entry, mock_webhook_client, dt.timedelta(minutes=10)
    )

    state = coordinator.data.schedules[DIRECTIVE_ID].state_at(dt_util.utcnow())
    assert state.current is None
    assert state.next_change == point.timestamp
    assert state.next_signal == point


async def test_active_last_slot_reports_its_end(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the end of the last active slot is a change to no signal."""
    coordinator, point = await _setup_single_slot_schedule(
        hass, mock_config_entry, mock_webhook_client, dt.timedelta(minutes=-5)
    )

    state = coordinator.data.schedules[DIRECTIVE_ID].state_at(dt_util.utcnow())
    assert state.current == point
    assert state.next_change == point.timestamp + dt.timedelta(minutes=15)
    assert state.next_signal is None


async def test_gap_between_slots_is_a_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a slot followed by a gap changes to no signal before the next slot."""
    resource, schedule = _directive_fixture()
    first, later = (
        DirectiveSignal(
            timestamp=dt_util.utcnow() + offset,
            signal="++",
            color="#00750e",
            raw_value=0,
        )
        for offset in (dt.timedelta(minutes=-5), dt.timedelta(minutes=30))
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(
        return_value=DirectiveData(
            title=schedule.title,
            description=schedule.description,
            interval=schedule.interval,
            data=(later, first),
        )
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    snapshot = coordinator.data.schedules[DIRECTIVE_ID]
    state = snapshot.state_at(dt_util.utcnow())
    assert state.current == first
    assert state.next_change == first.timestamp + dt.timedelta(minutes=15)
    assert state.next_signal is None
    after_gap = snapshot.state_at(state.next_change)
    assert after_gap.current is None
    assert after_gap.next_change == later.timestamp
    assert after_gap.next_signal == later


async def test_expired_schedule_has_no_signals(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a schedule that already ended has no current signal or next change."""
    coordinator, _ = await _setup_single_slot_schedule(
        hass, mock_config_entry, mock_webhook_client, dt.timedelta(hours=-3)
    )

    state = coordinator.data.schedules[DIRECTIVE_ID].state_at(dt_util.utcnow())
    assert state.current is None
    assert state.next_change is None
    assert state.next_signal is None


async def test_signal_change_updates_listeners_without_polling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test listeners are updated when a slot ends, before the next poll."""
    coordinator, point = await _setup_single_slot_schedule(
        hass, mock_config_entry, mock_webhook_client, dt.timedelta(minutes=-13)
    )
    listener = MagicMock()
    coordinator.async_add_listener(listener)
    polls = mock_webhook_client.get_directive_data.await_count

    freezer.move_to(point.timestamp + dt.timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    listener.assert_called_once()
    assert mock_webhook_client.get_directive_data.await_count == polls
    state = coordinator.data.schedules[DIRECTIVE_ID].state_at(dt_util.utcnow())
    assert state.current is None


async def test_failing_schedule_keeps_directive_granted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a directive whose schedule fails stays granted without a schedule."""
    resource, _ = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(
        side_effect=ClientError("upstream failed")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    assert coordinator.data.schedules == {}


async def test_unavailable_schedule_logged_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a directive schedule logs once when it goes unavailable and recovers."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(
        side_effect=ClientError("upstream failed")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data.schedules == {}
    assert caplog.text.count(f"EnergyID directive {DIRECTIVE_ID} is unavailable") == 1

    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert set(coordinator.data.schedules) == {DIRECTIVE_ID}
    assert f"EnergyID directive {DIRECTIVE_ID} is available again" in caplog.text


async def test_access_denied_means_no_directives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a device without directive access gets an empty grant, not an error."""
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=PermissionError("directives not granted")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert coordinator.last_update_success
    assert coordinator.data.resources == {}


async def test_startup_failure_does_not_block_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed first fetch leaves the entry loaded and recovers later."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=ClientError("EnergyID briefly unreachable")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)
    assert not coordinator.last_update_success
    assert "Unable to retrieve EnergyID directives" in caplog.text

    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success
    assert set(coordinator.data.resources) == {DIRECTIVE_ID}


async def test_unauthorized_at_startup_does_not_block_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a 401 on the first fetch leaves the entry loaded without reauth."""
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        )
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert not coordinator.last_update_success
    assert "Unable to retrieve EnergyID directives" in caplog.text
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_forbidden_means_no_directives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a 403 on the directive list means no directive is granted."""
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(), history=(), status=403
        )
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert coordinator.last_update_success
    assert coordinator.data.resources == {}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_access_granted_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test API access granted after setup is picked up on the next poll."""
    resource, schedule = _directive_fixture(good_slots=4)

    coordinator = await _setup_with_directives(hass, mock_config_entry)
    assert coordinator.data.resources == {}

    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    state = coordinator.data.schedules[DIRECTIVE_ID].state_at(dt_util.utcnow())
    assert state.current == schedule.data[0]
    # Slots with the same signal are not a change.
    assert state.next_change == schedule.data[4].timestamp
    assert state.next_signal == schedule.data[4]


async def _poll_with_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    status: int,
) -> EnergyIDDirectiveCoordinator:
    """Set up one directive, then let the next poll get an HTTP error."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    getattr(mock_webhook_client, method).side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=status
    )
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    return coordinator


@pytest.mark.parametrize("method", ["get_directives", "get_directive_data"])
async def test_unauthorized_while_polling_fails_update_without_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test a 401 that survives the client's own retry only fails the update."""
    coordinator = await _poll_with_error(
        hass, mock_config_entry, mock_webhook_client, freezer, method, 401
    )

    assert not coordinator.last_update_success
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_forbidden_while_polling_removes_directives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test access withdrawn while polling leaves no directives."""
    coordinator = await _poll_with_error(
        hass, mock_config_entry, mock_webhook_client, freezer, "get_directives", 403
    )

    assert coordinator.last_update_success
    assert coordinator.data.resources == {}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_forbidden_schedule_only_drops_that_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a 403 on one schedule keeps the directive but drops its schedule."""
    coordinator = await _poll_with_error(
        hass, mock_config_entry, mock_webhook_client, freezer, "get_directive_data", 403
    )

    assert coordinator.last_update_success
    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    assert coordinator.data.schedules == {}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_failed_schedule_waits_for_the_other_requests(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing schedule ends the refresh only after the others finished."""
    resource, schedule = _directive_fixture()
    other = replace(resource, id="22222222-2222-2222-2222-222222222222")
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource, other])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    finished: list[str] = []

    async def get_directive_data(directive_id: str) -> DirectiveData:
        if directive_id == DIRECTIVE_ID:
            raise ClientResponseError(request_info=MagicMock(), history=(), status=401)
        for _ in range(3):
            await asyncio.sleep(0)
        finished.append(directive_id)
        return schedule

    mock_webhook_client.get_directive_data = AsyncMock(side_effect=get_directive_data)
    finished_at_failure: list[str] = []
    coordinator.async_add_listener(
        lambda: (
            finished_at_failure.extend(finished)
            if not coordinator.last_update_success
            else None
        )
    )
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not coordinator.last_update_success
    assert finished_at_failure == [other.id]


async def test_schedule_server_error_keeps_directive_granted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a server error on one schedule only drops that schedule."""
    resource, _ = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(), history=(), status=500
        )
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert coordinator.last_update_success
    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    assert coordinator.data.schedules == {}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def _lose_claim_and_return_nothing(
    client: MagicMock, *_args: object
) -> list[DirectiveResource]:
    client.is_claimed = False
    return []


async def _lose_claim_and_deny(client: MagicMock, *_args: object) -> NoReturn:
    client.is_claimed = False
    raise PermissionError("The device is not authenticated")


async def _lose_claim_and_reject(client: MagicMock, *_args: object) -> NoReturn:
    client.is_claimed = False
    raise ClientResponseError(request_info=MagicMock(), history=(), status=401)


@pytest.mark.parametrize(
    ("method", "lose_claim"),
    [
        pytest.param(
            "get_directives", _lose_claim_and_return_nothing, id="get_directives"
        ),
        pytest.param(
            "get_directives", _lose_claim_and_deny, id="get_directives_denied"
        ),
        pytest.param(
            "get_directives", _lose_claim_and_reject, id="get_directives_rejected"
        ),
        pytest.param(
            "get_directive_data", _lose_claim_and_deny, id="get_directive_data"
        ),
        pytest.param(
            "get_directive_data",
            _lose_claim_and_reject,
            id="get_directive_data_rejected",
        ),
    ],
)
async def test_claim_lost_while_polling_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    lose_claim: Callable[..., Awaitable[Any]],
) -> None:
    """Test a claim lost during the client's own re-authentication starts reauth."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    getattr(mock_webhook_client, method).side_effect = partial(
        lose_claim, mock_webhook_client
    )
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not coordinator.last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_server_error_marks_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a server error while polling fails the update without reauthentication."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    mock_webhook_client.get_directives.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=500
    )
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not coordinator.last_update_success
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
