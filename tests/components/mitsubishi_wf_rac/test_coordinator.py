"""Test the Mitsubishi WF-RAC coordinator."""

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
import time
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pywfrac import (
    Aircon,
    AirconStat,
    RacParser,
    WfRacConnectionError,
    WfRacError,
    WfRacRegistrationError,
    WfRacWriteRefusedError,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
)
from homeassistant.components.mitsubishi_wf_rac.const import DOMAIN
from homeassistant.components.mitsubishi_wf_rac.coordinator import (
    WRITE_LOCK_RETRY_DELAY,
    registration_full_issue_id,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

DOMAIN_LOGGER = "homeassistant.components.mitsubishi_wf_rac"
ENTITY_ID = "climate.living_room"
POLL = timedelta(seconds=60)


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, polls: int):
    for _ in range(polls):
        freezer.tick(POLL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


async def test_a_missed_poll_does_not_go_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The module reassociates with the WiFi about once an hour on its own.

    Going unavailable on the first missed poll would report an outage every
    hour that nobody can act on, so the retry limit has to be spent first.
    """
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")

    await _advance(hass, freezer, 2)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    await _advance(hass, freezer, 1)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_the_airco_comes_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    aircon_stat: dict,
    init_integration: MockConfigEntry,
) -> None:
    """One good poll is enough to be available again."""
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")
    await _advance(hass, freezer, 3)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_repository.get_aircon_stats.side_effect = None
    mock_repository.get_aircon_stats.return_value = aircon_stat
    await _advance(hass, freezer, 1)

    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_an_evicted_account_re_registers_itself(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Register again after being evicted from the account table.

    Opening the manufacturer's app can push Home Assistant out of it. An
    evicted account still answers, so the failure is answered by registering
    again rather than by waiting.
    """
    mock_repository.update_account_info.reset_mock()
    mock_repository.get_aircon_stats.side_effect = KeyError("airconStat")

    await _advance(hass, freezer, 1)

    mock_repository.update_account_info.assert_awaited()


async def test_an_unreachable_airco_does_not_re_register(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Do not re-register over an outage.

    Registering cannot succeed over a connection that is not there, so a plain
    outage must not spend a request on it.
    """
    mock_repository.update_account_info.reset_mock()
    mock_repository.get_aircon_stats.side_effect = WfRacConnectionError("no route")

    await _advance(hass, freezer, 1)

    mock_repository.update_account_info.assert_not_awaited()


async def test_a_refused_write_is_retried_once_the_lock_lapses(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Another client's 60-second write lock is waited out, not fought.

    The delay comes from the unit's own `expires`, so the retry lands on the
    far side of the lapse instead of at a guessed interval.
    """
    aircon_stat = mock_repository.get_aircon_stats.return_value
    mock_repository.send_airco_command.side_effect = [
        WfRacWriteRefusedError("locked"),
        aircon_stat["airconStat"],
    ]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_repository.send_airco_command.await_count == 2


async def test_the_retry_waits_out_what_is_left_of_the_lock(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aircon_stat: dict,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The wait comes from the unit's own `expires`, not from a fixed interval.

    Getting the arithmetic wrong is invisible in the retry count: the command
    is sent either way, just back into a lock that has not lapsed yet.
    """
    freezer.move_to("2026-09-06T12:00:00+00:00")
    aircon_stat["expires"] = int(dt_util.utcnow().timestamp()) + 20
    mock_repository.send_airco_command.side_effect = [
        WfRacWriteRefusedError("locked"),
        aircon_stat["airconStat"],
    ]

    with patch(
        "homeassistant.components.mitsubishi_wf_rac.coordinator.asyncio.sleep"
    ) as sleep:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # 20 seconds left on the lock, plus the second that puts the retry on the
    # far side of the lapse.
    assert 21 in [call.args[0] for call in sleep.await_args_list]


async def test_an_evicted_account_re_registers_before_retrying(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Losing the account slot mid-command costs a registration, not the command."""
    aircon_stat = mock_repository.get_aircon_stats.return_value
    mock_repository.send_airco_command.side_effect = [
        WfRacRegistrationError("evicted"),
        aircon_stat["airconStat"],
    ]
    mock_repository.update_account_info.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.update_account_info.assert_awaited()
    assert mock_repository.send_airco_command.await_count == 2


async def test_a_full_account_table_raises_a_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """result:2 means the module has no free account slot left.

    Nothing the integration can do about it from here, so it says so in
    Repairs rather than retrying forever.
    """
    device = init_integration.runtime_data.device
    mock_repository.update_account_info.return_value = {"result": 2}

    await device.add_account()

    assert issue_registry.async_get_issue(
        DOMAIN, registration_full_issue_id(init_integration.entry_id)
    )


async def test_a_freed_account_table_clears_the_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The issue must not outlive the condition that raised it."""
    device = init_integration.runtime_data.device
    mock_repository.update_account_info.return_value = {"result": 2}
    await device.add_account()

    mock_repository.update_account_info.return_value = {"result": 0}
    await device.add_account()

    assert not issue_registry.async_get_issue(
        DOMAIN, registration_full_issue_id(init_integration.entry_id)
    )


@pytest.mark.parametrize(
    ("method", "mocked"),
    [("add_account", "update_account_info"), ("delete_account", "del_account_info")],
)
async def test_account_calls_swallow_their_errors(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    method: str,
    mocked: str,
) -> None:
    """Both run on paths that have nothing better to do with a failure."""
    device = init_integration.runtime_data.device
    getattr(mock_repository, mocked).side_effect = WfRacError("no answer")

    assert await getattr(device, method)() is None


async def test_unparseable_data_marks_the_airco_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """A frame that answers but does not parse is a failed poll like any other."""
    mock_repository.get_aircon_stats.return_value = {"airconStat": "not base64"}

    await _advance(hass, freezer, 3)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_a_poll_that_never_answers_counts_as_a_missed_poll(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The outer deadline can expire before the request's own does.

    That has to stay as quiet as any other missed poll, or a transient outage
    would mark the airco unavailable ahead of the configured threshold - and
    it must not become an update failure either, which is the difference
    between this and any other exception leaving the poll.
    """

    async def _never_answers(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(3600)

    mock_repository.get_aircon_stats.side_effect = _never_answers

    caplog.set_level(logging.DEBUG)

    with patch(
        "homeassistant.components.mitsubishi_wf_rac.coordinator.POLL_TIMEOUT",
        timedelta(seconds=0),
    ):
        await init_integration.runtime_data.device.async_refresh()

    assert "did not answer within 0s" in caplog.text
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
    assert init_integration.runtime_data.device.last_update_success


async def test_a_poll_that_fails_unexpectedly_is_an_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Only the expected failures are ridden out quietly.

    update() answers the ones this module knows about itself; anything else
    reaching the poll is a fault rather than the hourly reassociation, and has
    to be reported as one instead of being swallowed.
    """
    mock_repository.get_aircon_stats.side_effect = RuntimeError("boom")

    await _advance(hass, freezer, 1)

    assert not init_integration.runtime_data.device.last_update_success


@pytest.mark.parametrize(
    ("stats", "side_effect"),
    [
        pytest.param(None, WfRacError("no answer"), id="unit_does_not_answer"),
        pytest.param({"airconId": "0011223344aa"}, None, id="no_expires_reported"),
    ],
)
async def test_a_refused_write_falls_back_when_the_deadline_is_unreadable(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    stats: dict | None,
    side_effect: Exception | None,
) -> None:
    """Without a readable deadline the retry waits the fixed interval.

    The lock in the way was taken after the last poll, so the only deadline
    worth having comes from asking again - and when that answer is unusable
    there is nothing left to compute a wait from.
    """
    aircon_stat = mock_repository.get_aircon_stats.return_value
    mock_repository.send_airco_command.side_effect = [
        WfRacWriteRefusedError("locked"),
        aircon_stat["airconStat"],
    ]
    mock_repository.get_aircon_stats.return_value = stats
    mock_repository.get_aircon_stats.side_effect = side_effect

    with patch(
        "homeassistant.components.mitsubishi_wf_rac.coordinator.asyncio.sleep"
    ) as sleep:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert WRITE_LOCK_RETRY_DELAY.total_seconds() in [
        call.args[0] for call in sleep.await_args_list
    ]


async def test_shutdown_waits_for_a_command_already_on_the_wire(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """A flush that has taken its parameters still has to be shut down.

    It lets go of _consolidation_task at that point so a later command opens
    its own window, which used to leave shutdown with nothing to cancel: the
    send finished afterwards and published to entities that were gone. The
    module accepts one connection at a time and an unload is usually followed
    by a reload, so the orphan collides with the coordinator replacing it.
    """
    device = init_integration.runtime_data.device
    on_the_wire = asyncio.Event()

    async def _never_returns(*args: object, **kwargs: object) -> None:
        on_the_wire.set()
        await asyncio.Event().wait()

    with patch.object(device, "set_airco", side_effect=_never_returns):
        caller = asyncio.create_task(
            hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
                blocking=True,
            )
        )
        await asyncio.wait_for(on_the_wire.wait(), timeout=5)

        await device.async_shutdown()

    assert not device._running_flushes
    caller.cancel()
    with suppress(asyncio.CancelledError):
        await caller


async def test_an_unreadable_frame_survives_the_polls_that_carry_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The poll delivering a bad frame is itself a success.

    So it resets the device's missed-poll counter before the entities read
    the frame. An entity that counted its own decoding failure into that
    counter could never reach the threshold, and would keep reporting stale
    state as current however long the condition lasted.
    """
    device = init_integration.runtime_data.device
    decode = device._parser.translate_bytes

    def _unreadable(raw: str) -> Aircon:
        airco = decode(raw)
        airco.OperationMode = 99
        return airco

    with patch.object(device._parser, "translate_bytes", side_effect=_unreadable):
        await _advance(hass, freezer, 3)

    assert device.available
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


async def test_an_unexpected_poll_failure_takes_the_entities_with_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """A missed poll is ridden out; a fault is not.

    Only the expected failures leave the coordinator successful, so an
    entity that reads Device.available alone would keep showing stale state
    as current after an UpdateFailed.
    """
    mock_repository.get_aircon_stats.side_effect = RuntimeError("boom")

    await _advance(hass, freezer, 1)

    assert not init_integration.runtime_data.device.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_a_retried_write_does_not_revert_the_client_it_waited_for(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The frame is a full state block, not a delta.

    A refusal means another client holds the write lock, and by the time it
    lapses that client has changed something. Re-sending the block encoded
    before the refusal would send every one of those fields back as it was.
    """
    aircon_stat = mock_repository.get_aircon_stats.return_value
    theirs = RacParser().translate_bytes(aircon_stat["airconStat"])
    theirs.PresetTemp = 27.0
    mock_repository.get_aircon_stats.return_value = {
        **aircon_stat,
        "airconStat": RacParser().to_base64(AirconStat.from_aircon(theirs)),
        "expires": int(time.time()),
    }
    mock_repository.send_airco_command.side_effect = [
        WfRacWriteRefusedError("locked"),
        aircon_stat["airconStat"],
    ]

    with patch("homeassistant.components.mitsubishi_wf_rac.coordinator.asyncio.sleep"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        )
        await hass.async_block_till_done()

    retried = RacParser().translate_bytes(
        mock_repository.send_airco_command.await_args.args[1]
    )
    assert retried.PresetTemp == 27.0


async def test_a_deadline_that_is_not_a_timestamp_falls_back_too(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """The answer is usable, its deadline is not.

    Split from the cases above because this one needs a frame the retry can
    still be encoded from - only the deadline is unreadable.
    """
    aircon_stat = mock_repository.get_aircon_stats.return_value
    mock_repository.get_aircon_stats.return_value = {**aircon_stat, "expires": "soon"}
    mock_repository.send_airco_command.side_effect = [
        WfRacWriteRefusedError("locked"),
        aircon_stat["airconStat"],
    ]

    with patch(
        "homeassistant.components.mitsubishi_wf_rac.coordinator.asyncio.sleep"
    ) as sleep:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert WRITE_LOCK_RETRY_DELAY.total_seconds() in [
        call.args[0] for call in sleep.await_args_list
    ]


async def test_a_command_issued_during_a_poll_waits_for_what_it_brings(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """A poll on the wire is about to replace the state a command builds from.

    The frame is a full state block and the module takes one connection at a
    time, so a command encoded before that poll lands would queue behind it
    and then put every field back the way it was - undoing whatever the app
    or the remote had just changed. The same revert as on the refusal path,
    on the path a poll opens.
    """
    original = mock_repository.get_aircon_stats.return_value
    theirs = RacParser().translate_bytes(original["airconStat"])
    theirs.PresetTemp = 27.0
    fresh = {
        **original,
        "airconStat": RacParser().to_base64(AirconStat.from_aircon(theirs)),
    }

    polling = asyncio.Event()
    let_the_poll_answer = asyncio.Event()

    async def _poll_in_flight(*args: object, **kwargs: object) -> dict:
        polling.set()
        await let_the_poll_answer.wait()
        return fresh

    mock_repository.get_aircon_stats.side_effect = _poll_in_flight
    mock_repository.send_airco_command.return_value = fresh["airconStat"]

    poll = asyncio.create_task(init_integration.runtime_data.device.async_refresh())
    await asyncio.wait_for(polling.wait(), timeout=5)

    # Without the consolidation window the command reaches the point where it
    # encodes right away, which is what has to happen while the poll is still
    # on the wire for this to say anything.
    with patch(
        "homeassistant.components.mitsubishi_wf_rac.coordinator.UPDATE_CONSOLIDATION_PERIOD",
        timedelta(0),
    ):
        command = asyncio.create_task(
            hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
                blocking=True,
            )
        )
        for _ in range(10):
            await asyncio.sleep(0)

        let_the_poll_answer.set()
        await poll
        await command
        await hass.async_block_till_done()

    sent = RacParser().translate_bytes(
        mock_repository.send_airco_command.await_args.args[1]
    )
    assert sent.PresetTemp == 27.0


async def test_an_evicted_account_is_reported_once_not_every_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Being dropped from the account table is one outage, not one per poll.

    The unit answers throughout, so re-registration is attempted on every
    poll - and if the table is full it cannot succeed. Saying so once a
    minute for as long as that lasts buries the line that matters.
    """
    mock_repository.get_aircon_stats.side_effect = WfRacError("result 2")
    mock_repository.update_account_info.side_effect = WfRacError("table full")
    caplog.set_level(logging.INFO)

    await _advance(hass, freezer, 6)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    outage = [r for r in caplog.records if "is unavailable after" in r.message]
    assert len(outage) == 1
    assert outage[0].levelno == logging.INFO
    ours = [r for r in caplog.records if r.name.startswith(DOMAIN_LOGGER)]
    assert not [r for r in ours if r.levelno >= logging.WARNING]
