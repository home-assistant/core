"""Test OpenGarage cover entity."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_TOGGLE,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def _simulate_door_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    door_state: int,
) -> None:
    """Simulate the OpenGarage device reporting a new door state."""
    mock_opengarage.update_state.return_value = {"door": door_state, "name": "abcdef"}
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("door_state", "expected_state", "expected_position"),
    [
        (0, STATE_CLOSED, 0),
        (1, STATE_OPEN, 100),
    ],
    ids=["closed", "open"],
)
async def test_cover_position(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    door_state: int,
    expected_state: str,
    expected_position: int,
) -> None:
    """Test that current_cover_position reflects the door state."""
    mock_opengarage.push_button.return_value = 1
    await _simulate_door_state(hass, mock_opengarage, door_state)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == expected_position


async def test_cover_position_during_transition(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that current_cover_position is None during opening/closing transition."""
    mock_opengarage.push_button.return_value = 1
    await _simulate_door_state(hass, mock_opengarage, 0)

    # Open the cover - will be in OPENING state before update
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.OPENING
    assert ATTR_CURRENT_POSITION not in state.attributes


@pytest.mark.parametrize(
    (
        "initial_door_state",
        "initial_state",
        "initial_position",
        "final_door_state",
        "final_state",
        "final_position",
    ),
    [
        (0, STATE_CLOSED, 0, 1, STATE_OPEN, 100),
        (1, STATE_OPEN, 100, 0, STATE_CLOSED, 0),
    ],
    ids=["closed_to_open", "open_to_closed"],
)
async def test_toggle_cover(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    initial_door_state: int,
    initial_state: str,
    initial_position: int,
    final_door_state: int,
    final_state: str,
    final_position: int,
) -> None:
    """Test toggling the cover switches it to the opposite state."""
    mock_opengarage.push_button.return_value = 1
    await _simulate_door_state(hass, mock_opengarage, initial_door_state)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == initial_state
    assert state.attributes[ATTR_CURRENT_POSITION] == initial_position

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    await _simulate_door_state(hass, mock_opengarage, final_door_state)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == final_state
    assert state.attributes[ATTR_CURRENT_POSITION] == final_position


async def test_toggle_does_not_reuse_stale_close_direction(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test toggle direction is derived from position, not a stale cached direction.

    This is the regression test for issue #115827. A previous close records
    the "closing" direction internally; if a later toggle relies on that
    cached direction instead of the current position, it would incorrectly
    open an already-open cover instead of closing it.
    """
    mock_opengarage.push_button.return_value = 1
    await _simulate_door_state(hass, mock_opengarage, 1)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN

    # Toggle while open should close, recording the close direction.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )
    assert mock_opengarage.push_button.call_count == 1

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.CLOSING

    # Door still reports open while physically closing.
    await _simulate_door_state(hass, mock_opengarage, 1)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.CLOSING

    # Door finishes closing.
    await _simulate_door_state(hass, mock_opengarage, 0)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED

    # Someone reopens the door outside of HA.
    await _simulate_door_state(hass, mock_opengarage, 1)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN

    # Toggling now must close again, not reuse the stale close direction.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )
    assert mock_opengarage.push_button.call_count == 2

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.CLOSING


@pytest.mark.parametrize(
    (
        "initial_door_state",
        "service",
        "final_door_state",
        "final_state",
        "final_position",
    ),
    [
        (0, SERVICE_OPEN_COVER, 1, STATE_OPEN, 100),
        (1, SERVICE_CLOSE_COVER, 0, STATE_CLOSED, 0),
    ],
    ids=["open", "close"],
)
async def test_cover_command(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    initial_door_state: int,
    service: str,
    final_door_state: int,
    final_state: str,
    final_position: int,
) -> None:
    """Test explicit open/close commands."""
    mock_opengarage.push_button.return_value = 1
    await _simulate_door_state(hass, mock_opengarage, initial_door_state)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    await _simulate_door_state(hass, mock_opengarage, final_door_state)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == final_state
    assert state.attributes[ATTR_CURRENT_POSITION] == final_position
