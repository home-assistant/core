"""Tests for the Roomba periodic connection mode."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from roombapy import RoombaConnectionError, RoombaError

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.roomba.connection import (
    COMMAND_HOLD_SECONDS,
    MISSION_CHECK_SECONDS,
    PERIODIC_UPDATE_INTERVAL,
    TELEMETRY_MAX_SECONDS,
    TELEMETRY_QUIET_SECONDS,
)
from homeassistant.components.roomba.const import CONF_BLID, CONF_CONTINUOUS, DOMAIN
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_LOCATE,
    SERVICE_START,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

VACUUM_ENTITY_ID = "vacuum.test_roomba"


@pytest.fixture
def periodic_roomba(mock_roomba: AsyncMock) -> AsyncMock:
    """Make connect and disconnect toggle the connected flag."""

    async def _connect() -> None:
        mock_roomba.connected = True
        _publish(mock_roomba, {"batPct": 100})

    async def _disconnect() -> None:
        mock_roomba.connected = False

    mock_roomba.connect.side_effect = _connect
    mock_roomba.disconnect.side_effect = _disconnect
    return mock_roomba


def _publish(roomba: AsyncMock, reported: dict[str, object]) -> None:
    """Deliver a message from the robot to every registered callback."""
    for registration in roomba.register_on_message_callback.call_args_list:
        registration.args[0]({"state": {"reported": reported}})


def _set_phase(roomba: AsyncMock, phase: str) -> None:
    roomba.master_state["state"]["reported"]["cleanMissionStatus"]["phase"] = phase


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, *, continuous: bool
) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_CONTINUOUS: continuous})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _tick_until_done(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, *tasks: asyncio.Task[None]
) -> None:
    """Advance time in 1 s steps until tasks waiting for the robot finish."""
    for _ in range(TELEMETRY_MAX_SECONDS + 2):
        for _ in range(5):
            await asyncio.sleep(0)
        if all(task.done() for task in tasks):
            break
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
    for task in tasks:
        await task


def _call(hass: HomeAssistant, domain: str, service: str) -> asyncio.Task[None]:
    """Start a blocking service call on the vacuum entity."""
    return hass.async_create_task(
        hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
        )
    )


async def _call_while_ticking(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    domain: str,
    service: str,
) -> None:
    """Run a service call that waits for the robot's state."""
    await _tick_until_done(hass, freezer, _call(hass, domain, service))


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_periodic_releases_robot_after_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test the session is closed once the initial telemetry has arrived."""
    await _setup(hass, mock_config_entry, continuous=False)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    periodic_roomba.disconnect.assert_not_awaited()

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    periodic_roomba.disconnect.assert_awaited_once()
    assert not periodic_roomba.connected
    # The last known state stays visible while disconnected.
    assert hass.states.get(VACUUM_ENTITY_ID).state == "docked"


async def test_periodic_poll_reconnects_and_releases(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test each poll opens a short-lived session."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert periodic_roomba.connect.await_count == 1

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connect.await_count == 2
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert not periodic_roomba.connected


async def test_periodic_keeps_session_during_mission(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test the session stays open while cleaning and closes once docked."""
    _set_phase(periodic_roomba, "run")
    await _setup(hass, mock_config_entry, continuous=False)

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    periodic_roomba.disconnect.assert_not_awaited()
    assert periodic_roomba.connect.await_count == 1

    _set_phase(periodic_roomba, "charge")
    await _advance(hass, freezer, timedelta(seconds=MISSION_CHECK_SECONDS))
    periodic_roomba.disconnect.assert_awaited_once()
    assert not periodic_roomba.connected


async def test_periodic_command_connects_and_holds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a command reconnects and the session is held for a while."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert not periodic_roomba.connected

    await hass.services.async_call(
        VACUUM_DOMAIN, SERVICE_LOCATE, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
    )
    assert periodic_roomba.connect.await_count == 2
    periodic_roomba.send_command.assert_awaited_once_with("find", None)

    await _advance(hass, freezer, timedelta(seconds=COMMAND_HOLD_SECONDS - 1))
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=1))
    assert not periodic_roomba.connected


async def test_periodic_poll_failure_retries(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test an unreachable robot during a poll is retried on the next one."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    connect = periodic_roomba.connect.side_effect
    periodic_roomba.connect.side_effect = RoombaConnectionError
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not periodic_roomba.connected

    periodic_roomba.connect.side_effect = connect
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connect.await_count == 3
    assert periodic_roomba.connected


async def test_continuous_never_releases(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test continuous mode holds a single session."""
    await _setup(hass, mock_config_entry, continuous=True)

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL * 3)

    periodic_roomba.connect.assert_awaited_once()
    periodic_roomba.disconnect.assert_not_awaited()


async def test_options_flow_switches_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test turning continuous off reloads into periodic mode."""
    await _setup(hass, mock_config_entry, continuous=True)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_CONTINUOUS: False}
    )
    await hass.async_block_till_done()

    assert mock_config_entry.options == {CONF_CONTINUOUS: False}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    disconnects = periodic_roomba.disconnect.await_count

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert periodic_roomba.disconnect.await_count == disconnects + 1


async def test_polling_disabled_refreshes_on_request(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test that with polling disabled only update_entity opens a session."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_CONTINUOUS: False},
        pref_disable_polling=True,
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert not periodic_roomba.connected

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL * 3)
    periodic_roomba.connect.assert_awaited_once()

    await _call_while_ticking(hass, freezer, HA_DOMAIN, SERVICE_UPDATE_ENTITY)

    # update_entity returns once the state is in and the robot is released.
    assert periodic_roomba.connect.await_count == 2
    assert not periodic_roomba.connected


async def test_refresh_joins_poll_in_progress(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test update_entity during a poll waits for that poll's telemetry."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connected

    task = _call(hass, HA_DOMAIN, SERVICE_UPDATE_ENTITY)
    for _ in range(5):
        await asyncio.sleep(0)
    assert not task.done()

    await _tick_until_done(hass, freezer, task)
    # It joined the poll's session instead of opening another one.
    assert periodic_roomba.connect.await_count == 2
    assert not periodic_roomba.connected


async def test_unreachable_is_logged_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test losing and regaining the robot is logged once each."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    connect = periodic_roomba.connect.side_effect
    periodic_roomba.connect.side_effect = RoombaConnectionError
    for _ in range(3):
        await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert caplog.text.count("is unreachable") == 1

    periodic_roomba.connect.side_effect = connect
    for _ in range(2):
        await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
        await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert caplog.text.count("is reachable again") == 1


async def test_reconnect_after_dropped_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a session that dropped on its own is torn down before reconnecting."""
    reconnecting = False

    async def _connect() -> None:
        if reconnecting:
            raise RoombaError("Already connected")
        periodic_roomba.connected = True

    async def _disconnect() -> None:
        nonlocal reconnecting
        reconnecting = False
        periodic_roomba.connected = False

    periodic_roomba.connect.side_effect = _connect
    periodic_roomba.disconnect.side_effect = _disconnect
    _set_phase(periodic_roomba, "run")
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    # Wi-Fi drop mid-mission: the client is reconnecting in the background.
    periodic_roomba.connected = False
    reconnecting = True
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connected

    periodic_roomba.connected = False
    reconnecting = True
    await hass.services.async_call(
        VACUUM_DOMAIN, SERVICE_LOCATE, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
    )
    periodic_roomba.send_command.assert_awaited_once_with("find", None)


async def test_idle_release_stops_background_reconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a session that dropped while idle is torn down, not left retrying."""
    await _setup(hass, mock_config_entry, continuous=False)
    # Dropped on its own; the client would keep reconnecting in the background.
    periodic_roomba.connected = False

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    periodic_roomba.disconnect.assert_awaited_once()


async def test_no_session_after_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a late command does not reopen a session once Home Assistant stops."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.services.async_call(
        VACUUM_DOMAIN, SERVICE_LOCATE, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
    )

    periodic_roomba.connect.assert_awaited_once()
    assert not periodic_roomba.connected


async def test_slow_robot_gets_time_to_publish(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test the session stays open while the robot keeps publishing state."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connected

    # A 900-series robot trickles its state in over several seconds.
    for _ in range(8):
        await _advance(hass, freezer, timedelta(seconds=1))
        _publish(periodic_roomba, {"bin": {"present": True, "full": False}})
        assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert not periodic_roomba.connected


async def test_wifi_stats_do_not_extend_the_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test Wi-Fi-only messages do not count as the robot still publishing."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)

    await _advance(hass, freezer, timedelta(seconds=1))
    _publish(periodic_roomba, {"signal": {"rssi": -50}})
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS - 1))

    assert not periodic_roomba.connected


async def test_silent_robot_released_after_max_wait(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a robot that publishes nothing is released after the upper bound."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    async def _silent_connect() -> None:
        periodic_roomba.connected = True

    periodic_roomba.connect.side_effect = _silent_connect
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_MAX_SECONDS - 1))
    assert periodic_roomba.connected

    await _advance(hass, freezer, timedelta(seconds=1))
    assert not periodic_roomba.connected


@pytest.mark.parametrize(
    ("connect_seconds", "connected"),
    [
        pytest.param(15, True, id="slow_but_within_timeout"),
        pytest.param(31, False, id="beyond_timeout"),
    ],
)
async def test_poll_waits_for_slow_connect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
    connect_seconds: int,
    connected: bool,
) -> None:
    """Test a poll gives a slow robot 30 seconds to accept the connection."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    accepted = asyncio.Event()

    async def _slow_connect() -> None:
        await accepted.wait()
        periodic_roomba.connected = True

    periodic_roomba.connect.side_effect = _slow_connect
    freezer.tick(PERIODIC_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    for _ in range(connect_seconds):
        await asyncio.sleep(0)
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
    await asyncio.sleep(0)
    accepted.set()
    await hass.async_block_till_done()

    assert periodic_roomba.connected is connected


async def test_migration_drops_options_from_before_roombapy_2(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    periodic_roomba: AsyncMock,
) -> None:
    """Test old Continuous and Delay options are dropped, keeping a permanent session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.0.30", CONF_BLID: "blid123", CONF_PASSWORD: "pw"},
        options={CONF_CONTINUOUS: False, "delay": 1},
        unique_id="blid123",
        minor_version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.options == {}
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert periodic_roomba.connected
    periodic_roomba.disconnect.assert_not_awaited()


async def test_command_fails_cleanly_when_unreachable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a command to an unreachable robot raises a translated error."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    periodic_roomba.connect.side_effect = RoombaConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_LOCATE,
            {ATTR_ENTITY_ID: VACUUM_ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == "not_connected"
    periodic_roomba.send_command.assert_not_awaited()


async def test_empty_message_does_not_extend_the_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test messages without reported state do not count as the robot publishing."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)

    await _advance(hass, freezer, timedelta(seconds=1))
    # The connection handler registers last; entities do not handle a null state.
    on_message = periodic_roomba.register_on_message_callback.call_args_list[-1].args[0]
    on_message({"state": None})
    on_message({"state": {"reported": {}}})
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS - 1))

    assert not periodic_roomba.connected


async def test_command_logs_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a successful command after an outage logs that the robot is back."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    connect = periodic_roomba.connect.side_effect
    periodic_roomba.connect.side_effect = RoombaConnectionError
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    assert "is unreachable" in caplog.text

    periodic_roomba.connect.side_effect = connect
    await hass.services.async_call(
        VACUUM_DOMAIN, SERVICE_LOCATE, {ATTR_ENTITY_ID: VACUUM_ENTITY_ID}, blocking=True
    )

    assert "is reachable again" in caplog.text


@pytest.mark.parametrize(
    ("cycle", "connected"),
    [
        pytest.param("clean", True, id="recharging_mid_mission"),
        pytest.param("none", False, id="charging_after_mission"),
    ],
)
async def test_recharge_mid_mission_keeps_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
    cycle: str,
    connected: bool,
) -> None:
    """Test charging during a mission keeps the session, ordinary charging does not."""
    status = periodic_roomba.master_state["state"]["reported"]["cleanMissionStatus"]
    status.update(phase="charge", cycle=cycle)
    await _setup(hass, mock_config_entry, continuous=False)

    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    assert periodic_roomba.connected is connected


async def test_mission_released_after_docking_without_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a mission session is released after docking even with polling disabled."""
    _set_phase(periodic_roomba, "run")
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_CONTINUOUS: False},
        pref_disable_polling=True,
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert periodic_roomba.connected

    _set_phase(periodic_roomba, "charge")
    await _advance(hass, freezer, timedelta(seconds=MISSION_CHECK_SECONDS))

    assert not periodic_roomba.connected


async def test_failed_command_does_not_pin_the_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a failed command leaves no hold that keeps a later session open."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_CONTINUOUS: False},
        pref_disable_polling=True,
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    connect = periodic_roomba.connect.side_effect
    periodic_roomba.connect.side_effect = RoombaConnectionError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_LOCATE,
            {ATTR_ENTITY_ID: VACUUM_ENTITY_ID},
            blocking=True,
        )

    periodic_roomba.connect.side_effect = connect
    await _call_while_ticking(hass, freezer, HA_DOMAIN, SERVICE_UPDATE_ENTITY)

    assert not periodic_roomba.connected


async def test_start_uses_fresh_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test start resumes a mission paused while Home Assistant was disconnected."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert hass.states.get(VACUUM_ENTITY_ID).state == "docked"

    async def _connect_paused() -> None:
        periodic_roomba.connected = True
        status = periodic_roomba.master_state["state"]["reported"]["cleanMissionStatus"]
        status.update(phase="pause", cycle="clean")
        _publish(periodic_roomba, {"cleanMissionStatus": status})

    periodic_roomba.connect.side_effect = _connect_paused
    await _call_while_ticking(hass, freezer, VACUUM_DOMAIN, SERVICE_START)

    periodic_roomba.send_command.assert_awaited_once_with("resume", None)


async def test_stop_during_reconnect_releases_waiters(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test unloading while a refresh reconnects does not leave it waiting."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    torn_down = asyncio.Event()

    async def _slow_disconnect() -> None:
        await torn_down.wait()
        periodic_roomba.connected = False

    periodic_roomba.disconnect.side_effect = _slow_disconnect
    refresh = _call(hass, HA_DOMAIN, SERVICE_UPDATE_ENTITY)
    for _ in range(5):
        await asyncio.sleep(0)
    # The unload starts while the refresh tears down the previous session.
    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    for _ in range(20):
        await asyncio.sleep(0)
    torn_down.set()
    await unload
    for _ in range(5):
        await asyncio.sleep(0)

    assert refresh.done()
    assert not periodic_roomba.connected


async def test_old_settle_timer_does_not_mark_reconnect_fresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a dropped session's timer cannot let start skip the new state."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    # A poll opens a session that drops while its telemetry is settling.
    async def _silent_connect() -> None:
        periodic_roomba.connected = True

    periodic_roomba.connect.side_effect = _silent_connect
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    await _advance(hass, freezer, timedelta(seconds=20))
    periodic_roomba.connected = False
    accepted = asyncio.Event()

    async def _slow_connect() -> None:
        await accepted.wait()
        periodic_roomba.connected = True
        _publish(
            periodic_roomba,
            {"cleanMissionStatus": {"cycle": "none", "phase": "charge"}},
        )

    periodic_roomba.connect.side_effect = _slow_connect
    task = _call(hass, VACUUM_DOMAIN, SERVICE_START)
    # The reconnect outlasts the old session's 30 s deadline.
    for _ in range(15):
        await asyncio.sleep(0)
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
    accepted.set()
    for _ in range(5):
        await asyncio.sleep(0)
    periodic_roomba.send_command.assert_not_awaited()

    await _tick_until_done(hass, freezer, task)
    periodic_roomba.send_command.assert_awaited_once_with("start", None)


async def test_start_requires_mission_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test start fails instead of guessing when the robot omits its mission state."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_while_ticking(hass, freezer, VACUUM_DOMAIN, SERVICE_START)

    assert exc_info.value.translation_key == "no_mission_state"
    periodic_roomba.send_command.assert_not_awaited()


async def test_start_requires_phase_and_cycle(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a partial mission update does not count as the mission state."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    async def _partial_connect() -> None:
        periodic_roomba.connected = True
        _publish(periodic_roomba, {"cleanMissionStatus": {"phase": "pause"}})

    periodic_roomba.connect.side_effect = _partial_connect
    with pytest.raises(HomeAssistantError):
        await _call_while_ticking(hass, freezer, VACUUM_DOMAIN, SERVICE_START)

    periodic_roomba.send_command.assert_not_awaited()


async def test_start_after_background_recovery_requires_mission_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a session the client recovered on its own needs fresh mission state."""
    _set_phase(periodic_roomba, "run")
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    assert periodic_roomba.connected

    on_state = periodic_roomba.register_on_connection_state_callback.call_args.args[0]
    on_state("disconnected", "Wi-Fi drop")
    on_state("connected", None)
    with pytest.raises(HomeAssistantError):
        await _call_while_ticking(hass, freezer, VACUUM_DOMAIN, SERVICE_START)

    periodic_roomba.send_command.assert_not_awaited()


async def test_refresh_reconnects_when_settling_session_dropped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test update_entity does not join a session that dropped while settling."""
    assert await async_setup_component(hass, HA_DOMAIN, {})
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    periodic_roomba.connected = False

    await _call_while_ticking(hass, freezer, HA_DOMAIN, SERVICE_UPDATE_ENTITY)

    assert periodic_roomba.connect.await_count == 3


async def test_mission_fields_in_separate_messages(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test phase and cycle arriving in separate updates count as mission state."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    status = periodic_roomba.master_state["state"]["reported"]["cleanMissionStatus"]

    async def _split_connect() -> None:
        periodic_roomba.connected = True
        status.update(phase="pause", cycle="clean")
        _publish(periodic_roomba, {"cleanMissionStatus": {"phase": "pause"}})
        _publish(periodic_roomba, {"cleanMissionStatus": {"cycle": "clean"}})

    periodic_roomba.connect.side_effect = _split_connect
    await _call_while_ticking(hass, freezer, VACUUM_DOMAIN, SERVICE_START)

    periodic_roomba.send_command.assert_awaited_once_with("resume", None)


async def test_start_waits_for_state_after_background_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test start after the client recovers waits for the robot's new state."""
    _set_phase(periodic_roomba, "run")
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    on_state = periodic_roomba.register_on_connection_state_callback.call_args.args[0]
    on_state("disconnected", "Wi-Fi drop")
    on_state("connected", None)
    _set_phase(periodic_roomba, "pause")

    task = _call(hass, VACUUM_DOMAIN, SERVICE_START)
    for _ in range(5):
        await asyncio.sleep(0)
    assert not task.done()
    status = periodic_roomba.master_state["state"]["reported"]["cleanMissionStatus"]
    _publish(periodic_roomba, {"cleanMissionStatus": status})
    await _tick_until_done(hass, freezer, task)

    periodic_roomba.send_command.assert_awaited_once_with("resume", None)


async def test_cached_mission_does_not_pin_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test a reconnect without mission state is released despite a cached run phase."""
    await _setup(hass, mock_config_entry, continuous=False)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))
    # The robot reported a mission earlier, but this session only sends battery data.
    _set_phase(periodic_roomba, "run")

    await _advance(hass, freezer, PERIODIC_UPDATE_INTERVAL)
    await _advance(hass, freezer, timedelta(seconds=TELEMETRY_QUIET_SECONDS))

    assert not periodic_roomba.connected


async def test_partial_setup_state_is_not_mission_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    periodic_roomba: AsyncMock,
) -> None:
    """Test setup data without the full mission state does not count as it."""
    del periodic_roomba.master_state["state"]["reported"]["cleanMissionStatus"]["cycle"]
    await _setup(hass, mock_config_entry, continuous=False)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_while_ticking(hass, freezer, VACUUM_DOMAIN, SERVICE_START)

    assert exc_info.value.translation_key == "no_mission_state"
    periodic_roomba.send_command.assert_not_awaited()
