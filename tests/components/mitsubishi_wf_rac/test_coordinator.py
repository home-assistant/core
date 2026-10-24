"""Test the polling and command handling of the Mitsubishi WF-RAC coordinator."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import gc
import logging
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pywfrac import (
    AIRFLOW_UNKNOWN,
    Aircon,
    AirconCommands,
    AirconStat,
    RacParser,
    WfRacAccountTableFullError,
    WfRacCommandError,
    WfRacConnectionError,
    WfRacMalformedResponseError,
    WfRacWriteRefusedError,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_TURN_OFF,
    HVACMode,
)
from homeassistant.components.mitsubishi_wf_rac.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from . import POLL, advance_polls

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.living_room"
DOMAIN_LOGGER = "homeassistant.components.mitsubishi_wf_rac"


async def _set_fan_mode(hass: HomeAssistant, fan_mode: str = "high") -> None:
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )


async def _settle() -> None:
    """Let ready tasks run without waiting for the ones that are held."""
    for _ in range(10):
        await asyncio.sleep(0)


async def _tick_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fire one poll without waiting for anything that is held on the wire."""
    freezer.tick(POLL)
    async_fire_time_changed(hass)
    await _settle()


def _state(hass: HomeAssistant) -> str:
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    return state.state


class _HeldCommand:
    """A command that stays on the wire until it is released."""

    def __init__(self, mock_repository: MagicMock) -> None:
        self.on_the_wire = asyncio.Event()
        self.release = asyncio.Event()
        mock_repository.async_send_command.side_effect = self._send

    async def _send(self, airco_id: str, base: Aircon, params: Any) -> Aircon:
        self.on_the_wire.set()
        await self.release.wait()
        return replace(base, AirFlow=4)


@pytest.mark.usefixtures("init_integration")
async def test_a_missed_poll_does_not_go_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_repository: MagicMock
) -> None:
    """Two missed polls are ridden out; the third takes the entity down."""
    mock_repository.async_get_status.side_effect = WfRacConnectionError("no route")

    await advance_polls(hass, freezer, 2)
    assert _state(hass) == HVACMode.OFF

    await advance_polls(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_the_airco_comes_back(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_repository: MagicMock
) -> None:
    """One good poll is enough to be available again."""
    status = mock_repository.async_get_status.return_value
    mock_repository.async_get_status.side_effect = WfRacConnectionError("no route")
    await advance_polls(hass, freezer, 3)
    assert _state(hass) == STATE_UNAVAILABLE

    mock_repository.async_get_status.side_effect = None
    mock_repository.async_get_status.return_value = status
    await advance_polls(hass, freezer)

    assert _state(hass) == HVACMode.OFF


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WfRacConnectionError("no route"), id="unreachable"),
        pytest.param(WfRacMalformedResponseError("garbled"), id="garbled_answer"),
        pytest.param(WfRacCommandError("no fresh data"), id="refused"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_failed_polls_count_and_never_register(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
    error: Exception,
) -> None:
    """A failed poll never registers, as registering spends a permanent account slot."""
    mock_repository.async_get_status.side_effect = error

    await advance_polls(hass, freezer, 3)

    assert _state(hass) == STATE_UNAVAILABLE
    mock_repository.async_register.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_a_poll_that_never_answers_counts_as_a_missed_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The outer deadline can expire first and still counts as a missed poll."""

    async def _never_answers(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(3600)

    mock_repository.async_get_status.side_effect = _never_answers
    caplog.set_level(logging.DEBUG)

    await advance_polls(hass, freezer)
    freezer.tick(timedelta(seconds=56))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "did not answer within 55s" in caplog.text
    assert _state(hass) == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_an_unexpected_poll_failure_takes_the_entities_with_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_repository: MagicMock
) -> None:
    """A missed poll is ridden out; a fault is not."""
    mock_repository.async_get_status.side_effect = RuntimeError("boom")

    await advance_polls(hass, freezer)

    assert _state(hass) == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_a_reported_failure_ends_when_a_poll_answers_and_not_before(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_repository: MagicMock
) -> None:
    """Riding out a missed poll must not end an outage that is already reported."""
    status = mock_repository.async_get_status.return_value
    mock_repository.async_get_status.side_effect = RuntimeError("boom")
    await advance_polls(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE

    mock_repository.async_get_status.side_effect = WfRacConnectionError("no route")
    await advance_polls(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE

    mock_repository.async_get_status.side_effect = None
    mock_repository.async_get_status.return_value = status
    await advance_polls(hass, freezer)
    assert _state(hass) == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_an_outage_is_reported_once_not_every_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A unit that stays away is one outage, not one line per poll."""
    mock_repository.async_get_status.side_effect = WfRacConnectionError("no route")
    caplog.set_level(logging.INFO)

    await advance_polls(hass, freezer, 6)

    assert _state(hass) == STATE_UNAVAILABLE
    ours = [r for r in caplog.records if r.name.startswith(DOMAIN_LOGGER)]
    assert len([r for r in ours if r.levelno >= logging.INFO]) == 1


@pytest.mark.usefixtures("init_integration", "no_consolidation_window")
async def test_an_answered_command_counts_as_proof_of_life(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
) -> None:
    """An answered command resets the failure count."""
    mock_repository.async_get_status.side_effect = WfRacConnectionError("no route")
    await advance_polls(hass, freezer, 2)

    await _set_fan_mode(hass)

    # The command reset the count; otherwise this would be the third failure.
    await advance_polls(hass, freezer)
    assert _state(hass) == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_a_refused_write_reaches_the_caller(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """The library waits out another client's lock; what it gives up on is shown."""
    mock_repository.async_send_command.side_effect = WfRacWriteRefusedError("locked")

    with pytest.raises(HomeAssistantError, match="locked"):
        await _set_fan_mode(hass)


@pytest.mark.parametrize("aircon_fields", [{"AirFlow": AIRFLOW_UNKNOWN}])
@pytest.mark.usefixtures("init_integration")
async def test_a_state_that_cannot_be_encoded_fails_the_command_unsent(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """An unreadable fan step must not turn every command into a crash."""
    transmitted: list[str] = []

    async def encode_then_send(
        airco_id: str, base: Aircon, params: dict[AirconCommands, Any]
    ) -> Aircon:
        stat = AirconStat.from_aircon(base)
        for key, value in params.items():
            setattr(stat, key, value)
        transmitted.append(RacParser().to_base64(stat))
        return base

    mock_repository.async_send_command.side_effect = encode_then_send

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_unencodable"
    assert not transmitted


async def test_a_full_account_table_raises_a_repair_issue_until_a_write_goes_through(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A full account table raises a repair issue that an accepted write clears."""
    unit = mock_repository.async_send_command.side_effect
    mock_repository.async_send_command.side_effect = WfRacAccountTableFullError("full")
    with pytest.raises(HomeAssistantError):
        await _set_fan_mode(hass)

    (issue,) = issue_registry.issues.values()
    assert issue.domain == DOMAIN
    assert issue.translation_key == "too_many_devices"
    assert issue.translation_placeholders == {"device_name": "Living room"}
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False

    mock_repository.async_send_command.side_effect = WfRacCommandError("refused")
    with pytest.raises(HomeAssistantError):
        await _set_fan_mode(hass)
    assert len(issue_registry.issues) == 1

    mock_repository.async_send_command.side_effect = unit
    await _set_fan_mode(hass)
    assert not issue_registry.issues
    assert init_integration.state.value == "loaded"


@pytest.mark.usefixtures("init_integration", "no_consolidation_window")
async def test_a_poll_does_not_queue_behind_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A poll stands down while a command holds the connection."""
    held = _HeldCommand(mock_repository)
    caller = asyncio.create_task(_set_fan_mode(hass))
    await held.on_the_wire.wait()
    polls_before = mock_repository.async_get_status.await_count

    caplog.set_level(logging.DEBUG)
    for _ in range(5):
        await _tick_poll(hass, freezer)

    assert mock_repository.async_get_status.await_count == polls_before
    assert _state(hass) == HVACMode.OFF
    assert "did not answer within" not in caplog.text

    held.release.set()
    await caller


@pytest.mark.usefixtures("init_integration", "no_consolidation_window")
async def test_a_poll_standing_down_does_not_end_a_reported_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
) -> None:
    """A poll standing down must not report success; only a command's answer can."""
    polling = asyncio.Event()
    fail = asyncio.Event()

    async def _poll_that_fails(airco_id: str) -> None:
        polling.set()
        await fail.wait()
        raise RuntimeError("boom")

    mock_repository.async_get_status.side_effect = _poll_that_fails
    await _tick_poll(hass, freezer)
    await polling.wait()

    # Issued while the unit counts as available, queued behind the poll.
    held = _HeldCommand(mock_repository)
    caller = asyncio.create_task(_set_fan_mode(hass))
    await _settle()
    fail.set()
    await held.on_the_wire.wait()
    assert _state(hass) == STATE_UNAVAILABLE

    await _tick_poll(hass, freezer)
    assert _state(hass) == STATE_UNAVAILABLE

    held.release.set()
    await caller
    await hass.async_block_till_done()
    assert _state(hass) == HVACMode.OFF


@pytest.mark.usefixtures("no_consolidation_window")
async def test_shutdown_ends_a_waiting_caller_with_an_error(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """A command cancelled by the unload raises an error, not a bare CancelledError."""
    held = _HeldCommand(mock_repository)
    caller = asyncio.create_task(_set_fan_mode(hass))
    await held.on_the_wire.wait()

    await hass.config_entries.async_unload(init_integration.entry_id)

    with pytest.raises(HomeAssistantError, match="shutting down"):
        await caller


@pytest.mark.usefixtures("no_consolidation_window")
async def test_a_caller_that_is_cancelled_itself_stays_cancelled(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Our own cancellation is not ours to turn into an error."""
    held = _HeldCommand(mock_repository)
    caller = asyncio.create_task(_set_fan_mode(hass))
    await held.on_the_wire.wait()

    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller

    await hass.config_entries.async_unload(init_integration.entry_id)


@pytest.mark.usefixtures("init_integration", "no_consolidation_window")
async def test_a_command_issued_during_a_poll_waits_for_what_it_brings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
) -> None:
    """A command waits for a running poll, or it would revert what the poll brings."""
    status = mock_repository.async_get_status.return_value
    theirs = replace(status.aircon, PresetTemp=27.0)
    polling = asyncio.Event()
    let_the_poll_answer = asyncio.Event()

    async def _poll_in_flight(airco_id: str) -> Any:
        polling.set()
        await let_the_poll_answer.wait()
        status.aircon = theirs
        return status

    mock_repository.async_get_status.side_effect = _poll_in_flight
    await _tick_poll(hass, freezer)
    await polling.wait()

    command = asyncio.create_task(_set_fan_mode(hass))
    await _settle()
    let_the_poll_answer.set()
    await command

    base = mock_repository.async_send_command.await_args.args[1]
    assert base.PresetTemp == 27.0


@pytest.mark.usefixtures("no_consolidation_window")
async def test_a_failing_flush_nobody_waits_for_is_not_reported_unretrieved(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The only caller gives up; the flush still fails later, quietly."""
    on_the_wire = asyncio.Event()
    fail = asyncio.Event()

    async def _send(airco_id: str, base: Aircon, params: Any) -> Aircon:
        on_the_wire.set()
        await fail.wait()
        raise WfRacCommandError("refused")

    mock_repository.async_send_command.side_effect = _send
    caller = asyncio.create_task(_set_fan_mode(hass))
    await on_the_wire.wait()

    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    fail.set()
    await hass.async_block_till_done()
    gc.collect()

    assert "never retrieved" not in caplog.text
    assert "shielded" not in caplog.text
