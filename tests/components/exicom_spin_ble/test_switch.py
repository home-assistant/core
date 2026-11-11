"""Tests for the Spin EV Charger charging switch."""

import asyncio
from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from spinev_ble import (
    ChargerState,
    ChargerStatus,
    SpinEvCommandRejectedError,
    SpinEvError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.exicom_spin_ble.const import (
    CHARGING_INTERVAL,
    COMMAND_SETTLE_TIME,
    IDLE_INTERVAL,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration, setup_persistent
from .const import IDLE_STATUS, STATUS

CHARGING_SWITCH = "switch.123456789012_charging"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Set up only the switch platform."""
    with patch("homeassistant.components.exicom_spin_ble.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("mock_charger")
async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The switch platform registers the entities it is expected to."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        pytest.param(ChargerState.AVAILABLE, STATE_OFF, id="available"),
        pytest.param(ChargerState.IDLE, STATE_OFF, id="idle"),
        pytest.param(ChargerState.STARTING, STATE_ON, id="starting"),
        pytest.param(ChargerState.CHARGING, STATE_ON, id="charging"),
        # A vehicle pausing resumes without a command, so the switch stays on
        # rather than flapping mid-session.
        pytest.param(ChargerState.EV_SUSPENDED, STATE_ON, id="ev_suspended"),
        pytest.param(ChargerState.EVSE_SUSPENDED, STATE_ON, id="evse_suspended"),
        pytest.param(ChargerState.FINISHING, STATE_OFF, id="finishing"),
        # The charger still answers with a state the library does not know, so
        # the switch is unknown rather than unavailable.
        pytest.param(None, STATE_UNKNOWN, id="unrecognised"),
    ],
)
async def test_the_switch_follows_the_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    state: ChargerState | None,
    expected: str,
) -> None:
    """The switch is on for a whole session, including while it is paused."""
    mock_charger.async_get_status.return_value = replace(IDLE_STATUS, state=state)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CHARGING_SWITCH).state == expected


@pytest.mark.parametrize(
    ("service", "before", "after", "command", "expected"),
    [
        pytest.param(
            SERVICE_TURN_ON,
            IDLE_STATUS,
            replace(IDLE_STATUS, state=ChargerState.STARTING),
            "async_start_charging",
            STATE_ON,
            id="turn_on",
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            STATUS,
            IDLE_STATUS,
            "async_stop_charging",
            STATE_OFF,
            id="turn_off",
        ),
    ],
)
async def test_commands_reach_the_charger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
    service: str,
    before: ChargerStatus,
    after: ChargerStatus,
    command: str,
    expected: str,
) -> None:
    """A command is sent, the link handed back, and the charger re-read."""
    mock_charger.async_get_status.return_value = before
    await setup_integration(hass, mock_config_entry)
    mock_charger.async_get_status.reset_mock()
    mock_charger.async_disconnect.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: CHARGING_SWITCH}, blocking=True
    )

    getattr(mock_charger, command).assert_awaited_once()
    mock_charger.async_disconnect.assert_awaited()
    # The charger reports the old state for a moment after acknowledging.
    mock_charger.async_get_status.assert_not_awaited()

    mock_charger.async_get_status.return_value = after
    freezer.tick(COMMAND_SETTLE_TIME)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_get_status.assert_awaited_once()
    assert hass.states.get(CHARGING_SWITCH).state == expected


async def test_a_poll_right_after_a_command_waits_for_the_charger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll due just after a command reads only once the charger has settled."""
    mock_charger.async_get_status.return_value = IDLE_STATUS
    await setup_integration(hass, mock_config_entry)
    freezer.tick(IDLE_INTERVAL - timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CHARGING_SWITCH}, blocking=True
    )
    mock_charger.async_get_status.reset_mock()

    # The poll falls due inside the settle time and cancels the pending refresh.
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_charger.async_get_status.assert_not_awaited()

    mock_charger.async_get_status.return_value = replace(
        IDLE_STATUS, state=ChargerState.STARTING
    )
    freezer.tick(COMMAND_SETTLE_TIME)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_charger.async_get_status.assert_awaited_once()
    assert hass.states.get(CHARGING_SWITCH).state == STATE_ON


async def test_a_persistent_link_is_held_through_a_command(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """A command does not give up a slot the user chose to keep."""
    await setup_persistent(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: CHARGING_SWITCH},
        blocking=True,
    )

    mock_charger.async_stop_charging.assert_awaited_once()
    mock_charger.async_disconnect.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "translation_key", "released"),
    [
        # The charger answered, so a held link is still good.
        pytest.param(
            SpinEvCommandRejectedError("refused"),
            "command_rejected",
            False,
            id="rejected",
        ),
        pytest.param(SpinEvError("no reply"), "cannot_send", True, id="no_reply"),
    ],
)
async def test_a_failed_command_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    error: SpinEvError,
    translation_key: str,
    released: bool,
) -> None:
    """A command the charger refuses or never answers surfaces to the user."""
    mock_charger.async_get_status.return_value = IDLE_STATUS
    mock_charger.async_start_charging.side_effect = error
    await setup_persistent(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    assert mock_charger.async_disconnect.await_count == int(released)


async def test_teardown_waits_for_a_command_in_flight(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """Unloading hands the link back only once a running command is done."""
    await setup_persistent(hass, mock_config_entry)
    started = asyncio.Event()
    finish = asyncio.Event()
    order: list[str] = []

    async def start_charging() -> None:
        started.set()
        await finish.wait()
        order.append("start")

    mock_charger.async_start_charging.side_effect = start_charging
    mock_charger.async_disconnect.side_effect = lambda: order.append("disconnect")

    command = hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )
    )
    await started.wait()
    # Unload callbacks run newest first and the shutdown starts eagerly, so a
    # shutdown that does not wait disconnects before the command resumes.
    mock_config_entry.async_on_unload(finish.set)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await command

    assert order == ["start", "disconnect"]


async def test_a_command_queued_behind_teardown_is_refused(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """A command that only gets the link after unloading never reconnects."""
    await setup_persistent(hass, mock_config_entry)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def start_charging() -> None:
        started.set()
        await finish.wait()

    mock_charger.async_start_charging.side_effect = start_charging

    running = hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )
    )
    await started.wait()
    mock_charger.async_connect.reset_mock()
    queued = hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )
    )
    mock_config_entry.async_on_unload(finish.set)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await running

    with pytest.raises(HomeAssistantError) as err:
        await queued

    assert err.value.translation_key == "unloading"
    mock_charger.async_connect.assert_not_awaited()
    mock_charger.async_stop_charging.assert_not_awaited()


async def test_a_poll_waits_for_a_command_holding_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll arriving mid-command neither reads nor drops the link until it ends."""
    await setup_integration(hass, mock_config_entry)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def start_charging() -> None:
        started.set()
        await finish.wait()

    mock_charger.async_start_charging.side_effect = start_charging
    mock_charger.async_get_status.reset_mock()
    mock_charger.async_disconnect.reset_mock()

    command = hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )
    )
    await started.wait()
    freezer.tick(CHARGING_INTERVAL)
    # The poll starts eagerly, so one that does not wait is already through.
    async_fire_time_changed(hass)
    # Always lets the command finish, so a missing lock fails the test rather
    # than hanging it.
    try:
        mock_charger.async_get_status.assert_not_awaited()
        mock_charger.async_disconnect.assert_not_awaited()
    finally:
        finish.set()
    await command
    freezer.tick(COMMAND_SETTLE_TIME)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_charger.async_get_status.assert_awaited()


async def test_a_command_waits_for_a_poll_holding_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A command arriving mid-poll neither sends nor drops the link until it ends."""
    await setup_integration(hass, mock_config_entry)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def get_status() -> ChargerStatus:
        started.set()
        await finish.wait()
        return IDLE_STATUS

    mock_charger.async_get_status.side_effect = get_status
    mock_charger.async_disconnect.reset_mock()

    freezer.tick(CHARGING_INTERVAL)
    async_fire_time_changed(hass)
    await started.wait()
    # The command starts eagerly, so one that does not wait is already sent.
    command = hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )
    )
    # Always lets the poll finish, so a missing lock fails the test rather than
    # hanging it.
    try:
        mock_charger.async_start_charging.assert_not_awaited()
        mock_charger.async_disconnect.assert_not_awaited()
    finally:
        finish.set()
    await command
    await hass.async_block_till_done()

    mock_charger.async_start_charging.assert_awaited_once()
