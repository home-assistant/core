"""Tests for the acaia switch."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "switch.kitchen_lunar_ddeeff_keep_connected"


async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia switch."""

    with patch("homeassistant.components.acaia.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_defaults_to_on(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch is on by default, preserving the always-connected behavior."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_turning_off_disconnects_scale(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the switch off disconnects the scale."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.disconnect.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_turning_on_reconnects_scale(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the switch back on re-establishes the connection."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connect.reset_mock()
    mock_scale.connected = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.connect.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_switch_state_survives_reload_without_reconnecting(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch restores its last state across a config entry reload.

    The preference is read from config entry options during coordinator
    init, before the first refresh runs, so a restored "off" state must not
    cause the coordinator to reconnect the scale on that first refresh.
    """

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.connected = False
    mock_scale.connect.reset_mock()

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_scale.connect.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_switch_available_while_scale_disconnected(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch stays available even while the scale is disconnected.

    Unlike other entities, this one has to remain usable while disconnected
    since it is the control that reconnects the scale.
    """

    await setup_integration(hass, mock_config_entry)
    mock_scale.connected = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != "unavailable"


async def test_turning_on_while_connected_does_not_reconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the switch on while already connected keeps the connection."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connect.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.connect.assert_not_called()


def _switch_call(hass: HomeAssistant, service: str) -> asyncio.Task[None]:
    """Start a switch service call without waiting for it to finish."""
    return hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    )


async def _yield() -> None:
    """Let started tasks run until they block."""
    for _ in range(5):
        await asyncio.sleep(0)


def _block_connect(mock_scale: MagicMock) -> tuple[asyncio.Event, asyncio.Event]:
    """Make connect() block until released, returning (started, release)."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def _connect(**kwargs: bool) -> None:
        started.set()
        await release.wait()
        mock_scale.connected = True

    mock_scale.connect.side_effect = _connect
    return started, release


def _block_disconnect(mock_scale: MagicMock) -> tuple[asyncio.Event, asyncio.Event]:
    """Make disconnect() block until released, returning (started, release)."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def _disconnect() -> None:
        started.set()
        await release.wait()
        mock_scale.connected = False

    mock_scale.disconnect.side_effect = _disconnect
    return started, release


async def _start_pending_poll_connect(
    hass: HomeAssistant, mock_scale: MagicMock, freezer: FrozenDateTimeFactory
) -> asyncio.Event:
    """Start a polling reconnect that blocks in connect(), returning its release."""
    mock_scale.connected = False
    mock_scale.connect.reset_mock()
    connect_started, release_connect = _block_connect(mock_scale)

    async def _disconnect() -> None:
        mock_scale.connected = False

    mock_scale.disconnect.side_effect = _disconnect
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await connect_started.wait()
    return release_connect


async def test_turning_off_during_pending_connect_disconnects(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning off while a reconnect is in flight leaves the scale disconnected."""

    await setup_integration(hass, mock_config_entry)
    release_connect = await _start_pending_poll_connect(hass, mock_scale, freezer)

    turn_off = _switch_call(hass, SERVICE_TURN_OFF)
    await _yield()
    mock_scale.disconnect.assert_not_called()

    release_connect.set()
    await turn_off
    await hass.async_block_till_done()

    mock_scale.disconnect.assert_called_once()
    assert mock_scale.heartbeat_task is None
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_turning_on_during_pending_connect_does_not_connect_twice(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an off/on toggle while a reconnect is in flight waits for it."""

    await setup_integration(hass, mock_config_entry)
    release_connect = await _start_pending_poll_connect(hass, mock_scale, freezer)

    turn_off = _switch_call(hass, SERVICE_TURN_OFF)
    turn_on = _switch_call(hass, SERVICE_TURN_ON)
    await _yield()
    assert mock_scale.connect.call_count == 1

    release_connect.set()
    await turn_off
    await turn_on
    await hass.async_block_till_done()

    mock_scale.connect.assert_called_once()
    mock_scale.disconnect.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_off_on_off_during_pending_connect_does_not_reconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a turn-on queued behind a pending connect is dropped once turned off."""

    await setup_integration(hass, mock_config_entry)
    release_connect = await _start_pending_poll_connect(hass, mock_scale, freezer)

    calls = [
        _switch_call(hass, service)
        for service in (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF)
    ]
    await _yield()

    release_connect.set()
    for call in calls:
        await call
    await hass.async_block_till_done()

    mock_scale.connect.assert_called_once()
    mock_scale.disconnect.assert_called_once()
    assert not mock_scale.connected
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_turning_on_during_pending_disconnect_reconnects(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on while turning off is still disconnecting reconnects."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connect.reset_mock()
    mock_scale.connect.side_effect = None
    disconnect_started, release_disconnect = _block_disconnect(mock_scale)

    turn_off = _switch_call(hass, SERVICE_TURN_OFF)
    await disconnect_started.wait()
    turn_on = _switch_call(hass, SERVICE_TURN_ON)
    await _yield()
    mock_scale.connect.assert_not_called()

    release_disconnect.set()
    await turn_off
    await turn_on
    await hass.async_block_till_done()

    mock_scale.connect.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_turning_on_during_pending_idle_disconnect_reconnects(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning on while an idle disconnect is in progress reconnects."""

    await setup_integration(hass, mock_config_entry)
    await mock_config_entry.runtime_data.async_set_idle_timeout(5)
    mock_scale.connect.reset_mock()
    disconnect_started, release_disconnect = _block_disconnect(mock_scale)

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await disconnect_started.wait()
    turn_on = _switch_call(hass, SERVICE_TURN_ON)
    await _yield()
    mock_scale.connect.assert_not_called()

    release_disconnect.set()
    await turn_on
    await hass.async_block_till_done()

    mock_scale.connect.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
