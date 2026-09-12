"""Tests for the Gaposa cover platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverEntityFeature,
)
from homeassistant.components.gaposa.const import MOTION_DELAY, UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

LIVING_ROOM_ENTITY = "cover.living_room"
BEDROOM_ENTITY = "cover.bedroom"


async def test_cover_entities_created(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Both mock motors should produce cover entities at setup."""
    assert hass.states.get(LIVING_ROOM_ENTITY) is not None
    assert hass.states.get(BEDROOM_ENTITY) is not None


async def test_cover_initial_state_from_motor(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The Living Room motor is UP, the Bedroom motor is DOWN."""
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPEN
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_CLOSED


async def test_cover_supported_features(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Open, close and stop are all supported; no position control."""
    state = hass.states.get(LIVING_ROOM_ENTITY)
    expected = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == expected
    assert ATTR_CURRENT_POSITION not in state.attributes


async def test_open_cover_calls_motor_up(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Calling open_cover invokes the mocked Motor.up()."""
    living_room_motor = mock_motors[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    living_room_motor.up.assert_called_once_with(False)


async def test_close_cover_calls_motor_down(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Calling close_cover invokes the mocked Motor.down()."""
    bedroom_motor = mock_motors[1]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    bedroom_motor.down.assert_called_once_with(False)


async def test_stop_cover_calls_motor_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Calling stop_cover invokes the mocked Motor.stop()."""
    living_room_motor = mock_motors[0]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    living_room_motor.stop.assert_called_once_with(False)


async def test_stop_leaves_state_unknown_until_poll(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A stop mid-motion parks the cover in STATE_UNKNOWN until the poll confirms STOP.

    The bedroom motor's steady-state is DOWN. After we open it and
    then stop, the physical cover is somewhere between endpoints —
    reporting the pre-stop endpoint would be wrong.
    """
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_UNKNOWN


async def test_stop_on_idle_cover_keeps_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Stopping an idle cover should not park it in STATE_UNKNOWN.

    Living room is idle at STATE_OPEN. A stop with no motion in
    flight is a no-op, so the entity should remain at STATE_OPEN
    rather than falsely reporting unknown for MOTION_DELAY seconds.
    """
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPEN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPEN


async def test_reopen_after_stop_reports_opening(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Re-opening a cover during the post-stop window should show STATE_OPENING.

    Living room starts at STATE_OPEN with motor.state=UP. Close
    starts motion; a stop then arms the post-stop window; a fresh
    open must arm a new motion window and switch to STATE_OPENING
    even though motor.state is still UP and _last_command is STOP.
    """
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_UNKNOWN

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPENING


async def test_reversal_mid_motion_switches_direction(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Reversing mid-motion should switch the reported direction immediately.

    The mock motor.state stays at its starting value (bedroom=DOWN)
    until pygaposa polls, so a naive endpoint check would leave
    _last_command pinned to the first command and keep the entity
    reporting the wrong direction after the reversal.
    """
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_CLOSING


async def test_cover_reports_opening_during_motion_window(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """After an open command the cover state is `opening` until MOTION_DELAY elapses."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(BEDROOM_ENTITY).state == STATE_OPENING


async def test_cover_reports_closing_during_motion_window(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """After a close command the cover state is `closing` until MOTION_DELAY elapses."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: LIVING_ROOM_ENTITY},
        blocking=True,
    )
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_CLOSING


@pytest.mark.parametrize(
    ("motor_state", "expected"),
    [
        ("UP", STATE_OPEN),
        ("DOWN", STATE_CLOSED),
        ("STOP", STATE_UNKNOWN),
        ("UNKNOWN", STATE_UNKNOWN),
    ],
)
async def test_cover_state_mapping(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
    motor_state: str,
    expected: str,
) -> None:
    """Verify the motor.state → HA state mapping across known + unknown values."""
    motor = mock_motors[0]
    motor.state = motor_state

    later = dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL + 1)
    async_fire_time_changed(hass, later)
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_ROOM_ENTITY).state == expected


async def test_cover_device_registry_entries(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Each motor ends up as a distinct device in the registry."""
    devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert len(devices) == 2
    assert {d.name for d in devices} == {"Living Room", "Bedroom"}


async def test_device_listener_pushes_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_gaposa: MagicMock,
    mock_motors: list[MagicMock],
) -> None:
    """A device listener firing publishes fresh motor state without a full coordinator poll."""
    device = mock_gaposa.clients[0][0].devices[0]
    assert device.addListener.called
    listener = device.addListener.call_args[0][0]

    mock_motors[0].state = "DOWN"
    listener()
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_CLOSED


async def test_motion_window_collapses_after_delay(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Past MOTION_DELAY, the cover should return to a steady state."""
    now = dt_util.utcnow()

    with freeze_time(now):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: BEDROOM_ENTITY},
            blocking=True,
        )

    later = now + timedelta(seconds=MOTION_DELAY + 5)
    with freeze_time(later):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

        state = hass.states.get(BEDROOM_ENTITY).state
        assert state not in (STATE_OPENING, STATE_CLOSING)
