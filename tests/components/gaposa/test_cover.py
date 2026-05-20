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
from homeassistant.components.gaposa.const import MOTION_DELAY
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
    living_room_motor.stop.assert_called_once_with(True)


async def test_stop_cancels_pending_motion_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A stop command mid-motion cancels the pending motion refresh."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )

    entity = hass.data["entity_components"]["cover"].get_entity(BEDROOM_ENTITY)
    assert entity._cancel_motion_refresh is not None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entity._cancel_motion_refresh is None


async def test_cover_reports_opening_during_motion_window(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """After an open command the cover state is `opening` until MOTION_DELAY elapses."""
    now = dt_util.utcnow()

    with freeze_time(now):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: BEDROOM_ENTITY},
            blocking=True,
        )

    assert hass.states.get(BEDROOM_ENTITY).state == STATE_OPENING


async def test_cover_reports_closing_during_motion_window(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """After a close command the cover state is `closing` until MOTION_DELAY elapses."""
    now = dt_util.utcnow()

    with freeze_time(now):
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

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_ROOM_ENTITY).state == expected


async def test_cover_device_registry_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Each motor ends up as a distinct device in the registry."""
    device_registry = dr.async_get(hass)
    gaposa_devices = [
        d
        for d in device_registry.devices.values()
        if any(i[0] == "gaposa" for i in d.identifiers)
    ]
    assert len(gaposa_devices) == 2
    names = {d.name for d in gaposa_devices}
    assert names == {"Living Room", "Bedroom"}


async def test_entity_reads_state_from_current_coordinator_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
) -> None:
    """Entity state should come from coordinator.data, not a cached Motor.

    This test replaces the Motor object in coordinator.data with a
    brand-new mock and verifies the entity reports the replacement's
    state.
    """
    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_OPEN

    coordinator = init_integration.runtime_data
    original_key = "DEVICE123.motors.motor-1"
    assert original_key in coordinator.data

    replacement = MagicMock()
    replacement.id = "motor-1"
    replacement.name = "Living Room"
    replacement.state = "DOWN"
    coordinator.data[original_key] = replacement
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    assert hass.states.get(LIVING_ROOM_ENTITY).state == STATE_CLOSED


async def test_rapid_open_close_replaces_motion_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A second open/close cancels the first motion refresh callback."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    entity = hass.data["entity_components"]["cover"].get_entity(BEDROOM_ENTITY)
    first_cancel = entity._cancel_motion_refresh
    assert first_cancel is not None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: BEDROOM_ENTITY},
        blocking=True,
    )
    assert entity._cancel_motion_refresh is not first_cancel


async def test_motion_window_collapses_after_delay(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_motors: list[MagicMock],
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
