"""Tests for the UniFi Protect siren (Public API) entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import (
    ModelType,
    PublicBootstrap,
    PublicSirenStatus,
    Siren,
    SirenDuration,
)
from uiprotect.exceptions import ClientError, NotAuthorized
from uiprotect.websocket import WebsocketState

from homeassistant.components.siren import ATTR_DURATION, ATTR_VOLUME_LEVEL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .utils import MockUFPFixture, assert_entity_counts, init_entry

from tests.common import async_fire_time_changed

SIREN_ID = "siren-id-1"
SIREN_MAC = "AA:BB:CC:DD:EE:02"
SIREN_NAME = "Garage Siren"

SIREN_ENTITY_ID = "siren.garage_siren"


def _make_siren(*, is_active: bool = False) -> Mock:
    """Build a mock :class:`Siren`."""
    status = Mock(spec=PublicSirenStatus)
    status.is_active = is_active
    status.activated_at = None
    status.duration = None
    status.turn_off_at = None
    siren = Mock(spec=Siren)
    siren.id = SIREN_ID
    siren.mac = SIREN_MAC
    siren.name = SIREN_NAME
    siren.model = ModelType.SIREN
    siren.volume = 50
    siren.siren_status = status
    siren.is_active = is_active
    siren.play = AsyncMock()
    siren.stop = AsyncMock()
    siren.set_volume = AsyncMock()
    return siren


def _make_public_bootstrap(siren: Mock | None) -> Mock:
    """Build a public bootstrap mock with the given siren."""
    pb = Mock(spec=PublicBootstrap)
    pb.sirens = {siren.id: siren} if siren is not None else {}
    pb.relays = {}
    pb.arm_mode = None
    pb.arm_profiles = {}
    return pb


def _make_ws_msg(siren: Mock, *, deleted: bool = False) -> Mock:
    """Build a minimal WS subscription message for siren tests."""
    msg = Mock()
    msg.changed_data = {}
    msg.old_obj = siren
    msg.new_obj = None if deleted else siren
    return msg


@pytest.fixture(name="siren")
def _siren_fixture() -> Mock:
    """Build a mock Siren."""
    return _make_siren()


@pytest.fixture(name="ufp_with_siren")
def _ufp_with_siren(ufp: MockUFPFixture, siren: Mock) -> MockUFPFixture:
    """Configure ufp fixture with a single siren accessible via public API."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(siren)
    return ufp


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def test_siren_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """No siren entity is created when public bootstrap is unavailable."""
    ufp.api.has_public_bootstrap = False
    await init_entry(hass, ufp, [])

    assert_entity_counts(hass, Platform.SIREN, 0, 0)


async def test_siren_created_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Siren entity is created with state off when siren is idle."""
    await init_entry(hass, ufp_with_siren, [])

    entry = entity_registry.async_get(SIREN_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{SIREN_MAC}_siren"

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_created_on(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Siren entity is created with state on when siren is active."""
    siren.is_active = True

    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def test_siren_turn_on(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Calling turn_on activates the siren via play()."""
    await init_entry(hass, ufp_with_siren, [])

    await hass.services.async_call(
        Platform.SIREN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
        blocking=True,
    )
    siren.play.assert_awaited_once_with(duration=None)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (5, SirenDuration.FIVE),
        (10, SirenDuration.TEN),
        (20, SirenDuration.TWENTY),
        (30, SirenDuration.THIRTY),
    ],
)
async def test_siren_turn_on_with_duration(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
    seconds: int,
    expected: SirenDuration,
) -> None:
    """Passing a valid duration to turn_on calls play with the matching SirenDuration."""
    await init_entry(hass, ufp_with_siren, [])

    await hass.services.async_call(
        Platform.SIREN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID, ATTR_DURATION: seconds},
        blocking=True,
    )
    siren.play.assert_awaited_once_with(duration=expected)


async def test_siren_turn_on_invalid_duration(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Passing an unsupported duration raises ServiceValidationError."""
    await init_entry(hass, ufp_with_siren, [])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID, ATTR_DURATION: 15},
            blocking=True,
        )
    siren.play.assert_not_awaited()


async def test_siren_turn_on_invalid_duration_does_not_set_volume(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Duration is validated before set_volume is called.

    When both an invalid duration and a volume are given, neither set_volume nor
    play must be called — duration validation must happen first.
    """
    await init_entry(hass, ufp_with_siren, [])

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: SIREN_ENTITY_ID,
                ATTR_DURATION: 15,
                ATTR_VOLUME_LEVEL: 0.5,
            },
            blocking=True,
        )
    siren.set_volume.assert_not_awaited()
    siren.play.assert_not_awaited()


async def test_siren_turn_on_with_volume(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Passing volume_level to turn_on calls set_volume before play."""
    await init_entry(hass, ufp_with_siren, [])

    await hass.services.async_call(
        Platform.SIREN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID, ATTR_VOLUME_LEVEL: 0.75},
        blocking=True,
    )
    siren.set_volume.assert_awaited_once_with(75)
    siren.play.assert_awaited_once_with(duration=None)


async def test_siren_turn_off(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Calling turn_off stops the siren via stop() and immediately sets state to off."""
    siren.is_active = True
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        Platform.SIREN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
        blocking=True,
    )
    siren.stop.assert_awaited_once()
    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [NotAuthorized("denied"), ClientError("timeout")],
)
async def test_siren_turn_on_api_error(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
    exc: Exception,
) -> None:
    """API errors from play() are wrapped as HomeAssistantError."""
    await init_entry(hass, ufp_with_siren, [])

    siren.play.side_effect = exc

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
            blocking=True,
        )


async def test_siren_turn_on_when_siren_gone(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Command raises HomeAssistantError when siren is no longer in bootstrap."""
    await init_entry(hass, ufp_with_siren, [])

    ufp_with_siren.api.public_bootstrap.sirens = {}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
            blocking=True,
        )


async def test_siren_turn_off_when_bootstrap_unavailable(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Command raises HomeAssistantError when has_public_bootstrap is False."""
    await init_entry(hass, ufp_with_siren, [])

    ufp_with_siren.api.has_public_bootstrap = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# WebSocket state updates
# ---------------------------------------------------------------------------


async def test_siren_state_updates_from_public_ws(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """A public devices WS update for the siren refreshes the entity state."""
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    siren.is_active = True

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_siren_ws_update_no_state_change(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """WS update with identical state leaves the entity state unchanged."""
    siren.is_active = True
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_siren_availability_follows_websocket_state(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
) -> None:
    """Siren entity becomes unavailable on WS disconnect and recovers on reconnect."""
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    assert ufp_with_siren.ws_state_subscription is not None
    ufp_with_siren.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    ufp_with_siren.ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_auto_off_after_timed_duration(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """State flips to OFF automatically when a timed duration expires.

    The public devices WS never sends an 'off' event for timed runs, so the
    entity must schedule its own callback via async_call_later.
    """
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Simulate a WS update: siren becomes active for 10 seconds.
    now = dt_util.utcnow()

    active_status = Mock(spec=PublicSirenStatus)
    active_status.is_active = True
    active_status.activated_at = int(now.timestamp() * 1000)
    active_status.duration = 10000
    active_status.turn_off_at = (
        None  # implementation uses activated_at+duration directly
    )

    siren.is_active = True
    siren.siren_status = active_status

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Advance HA time past turn_off_at — the scheduled callback should fire.
    async_fire_time_changed(hass, now + timedelta(seconds=11))
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_turn_off_cancels_scheduled_timer(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Manual turn_off cancels the pending auto-off timer.

    When a timed run is active the entity holds a scheduled callback.  A
    manual turn_off must cancel that callback so the timer never fires and
    the state stays OFF afterwards.
    """
    await init_entry(hass, ufp_with_siren, [])

    # Start a timed run — schedules an auto-off callback 30 s from now.
    now = dt_util.utcnow()
    active_status = Mock(spec=PublicSirenStatus)
    active_status.is_active = True
    active_status.activated_at = int(now.timestamp() * 1000)
    active_status.duration = 30000  # 30 s — won't expire on its own
    active_status.turn_off_at = None

    siren.is_active = True
    siren.siren_status = active_status

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Manually turn off — must cancel the scheduled timer.
    await hass.services.async_call(
        Platform.SIREN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SIREN_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Advance time past the original timer — state must stay OFF.
    async_fire_time_changed(hass, now + timedelta(seconds=35))
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_auto_off_when_already_expired_at_update(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """State flips to OFF when a WS update arrives with an already-expired duration.

    On reconnect, the public bootstrap may still report is_active=True with an
    activated_at+duration that is already in the past.  The entity must treat
    delay<=0 as immediately expired and set its state to OFF immediately.
    """
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Build a status whose turn-off time is 5 seconds in the PAST.
    now = dt_util.utcnow()
    expired_activated_at = int((now.timestamp() - 15) * 1000)  # 15 s ago

    expired_status = Mock(spec=PublicSirenStatus)
    expired_status.is_active = True
    expired_status.activated_at = expired_activated_at
    expired_status.duration = 10000  # 10 s → expired 5 s ago
    expired_status.turn_off_at = None

    siren.is_active = True
    siren.siren_status = expired_status

    mock_msg = _make_ws_msg(siren)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    # Entity stays OFF: delay<=0 overrides is_active=True inline, so the state
    # machine never sees ON.
    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_siren_unavailable_on_delete_event(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Entity becomes UNAVAILABLE when the siren is removed via a WS delete event.

    When the public bootstrap sends new_obj=None (device deleted), data.py
    dispatches the last-known Siren object (old_obj) to subscriptions.
    The entity then checks self._siren; if it is no longer in the bootstrap
    it must override _attr_available to False.
    """
    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    # Remove the siren from the public bootstrap so _siren returns None.
    del ufp_with_siren.api.public_bootstrap.sirens[SIREN_ID]

    # Simulate a WS delete event: new_obj=None, old_obj=last-known siren.
    mock_msg = _make_ws_msg(siren, deleted=True)
    assert ufp_with_siren.devices_ws_subscription is not None
    ufp_with_siren.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_siren_auto_off_timer_scheduled_at_startup(
    hass: HomeAssistant,
    ufp_with_siren: MockUFPFixture,
    siren: Mock,
) -> None:
    """Auto-off timer is scheduled during async_added_to_hass for an already-active siren.

    If a timed run is already in progress when HA starts, the entity must
    schedule its own auto-off callback immediately (not wait for a WS update)
    so the siren does not remain stuck ON after the run expires.
    """
    # Configure the siren as already active with 10 s remaining.
    now = dt_util.utcnow()
    active_status = Mock(spec=PublicSirenStatus)
    active_status.is_active = True
    active_status.activated_at = int(now.timestamp() * 1000)
    active_status.duration = 10000
    active_status.turn_off_at = None

    siren.is_active = True
    siren.siren_status = active_status

    await init_entry(hass, ufp_with_siren, [])

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Advance HA time past the expiry — the startup-scheduled timer must fire.
    async_fire_time_changed(hass, now + timedelta(seconds=11))
    await hass.async_block_till_done()

    state = hass.states.get(SIREN_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
