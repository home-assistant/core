"""Test OpenGarage cover entity."""

from unittest.mock import MagicMock

import aiohttp
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_TOGGLE,
    CoverState,
)
from homeassistant.components.opengarage.coordinator import (
    OpenGarageDataUpdateCoordinator,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _simulate_door_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    coordinator: OpenGarageDataUpdateCoordinator,
    door_state: int,
) -> None:
    """Simulate the OpenGarage device reporting a new door state."""
    mock_opengarage.update_state.return_value = {"door": door_state, "name": "abcdef"}
    await coordinator.async_refresh()
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
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, door_state)

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
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, 0)

    # Open the cover - will be in OPENING state before update
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.OPENING
    assert (
        ATTR_CURRENT_POSITION not in state.attributes
        or state.attributes[ATTR_CURRENT_POSITION] is None
    )


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
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, initial_door_state)

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

    await _simulate_door_state(hass, mock_opengarage, coordinator, final_door_state)

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
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, 1)

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
    await _simulate_door_state(hass, mock_opengarage, coordinator, 1)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.CLOSING

    # Door finishes closing.
    await _simulate_door_state(hass, mock_opengarage, coordinator, 0)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED

    # Someone reopens the door outside of HA.
    await _simulate_door_state(hass, mock_opengarage, coordinator, 1)

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
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, initial_door_state)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    await _simulate_door_state(hass, mock_opengarage, coordinator, final_door_state)

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == final_state
    assert state.attributes[ATTR_CURRENT_POSITION] == final_position


@pytest.mark.parametrize(
    ("push_button_result", "log_message"),
    [
        (None, "Unable to connect to OpenGarage device"),
        (2, "Device key is incorrect"),
        (3, "Error code 3"),
    ],
    ids=["connection_error", "bad_device_key", "other_error_code"],
)
async def test_push_button_error_code_rolls_back_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    push_button_result: int | None,
    log_message: str,
) -> None:
    """Test that a failed push_button result restores and publishes the prior state."""
    mock_opengarage.push_button.return_value = push_button_result
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, 0)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert log_message in caplog.text
    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize(
    "side_effect",
    [aiohttp.ClientError(), TimeoutError()],
    ids=["client_error", "timeout_error"],
)
async def test_push_button_raises_rolls_back_state_and_reraises(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test that push_button raising restores and publishes the prior state, then re-raises."""
    mock_opengarage.push_button.side_effect = side_effect
    coordinator = init_integration.runtime_data
    await _simulate_door_state(hass, mock_opengarage, coordinator, 0)

    with pytest.raises(type(side_effect)):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.garage_abcdef"},
            blocking=True,
        )

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
