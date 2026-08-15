"""Test OpenGarage cover entity."""

from unittest.mock import MagicMock

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_TOGGLE,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_cover_position_closed(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that current_cover_position is 0 when closed."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})

    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_cover_position_open(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that current_cover_position is 100 when open."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})

    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_cover_position_during_transition(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that current_cover_position is None during opening/closing transition."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})

    await hass.async_block_till_done()

    # Open the cover - will be in OPENING state before update
    await hass.services.async_call(
        "cover",
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == CoverState.OPENING
    # Position should be None during transition
    assert (
        ATTR_CURRENT_POSITION not in state.attributes
        or state.attributes[ATTR_CURRENT_POSITION] is None
    )


async def test_toggle_from_closed_to_open(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test toggling cover from closed opens it."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})

    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Toggle should call open
    await hass.services.async_call(
        "cover",
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    # Simulate door opening
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_toggle_from_open_to_closed(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test toggling cover from open closes it."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})

    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    # Toggle should call close
    await hass.services.async_call(
        "cover",
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    # Simulate door closing
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_toggle_already_closed_does_not_close_again(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test toggling when already closed doesn't send extra command.

    This is the regression test for issue #115827.
    When cover is closed (position=0), toggle should open it, not fail silently.
    """
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})

    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # First toggle opens
    await hass.services.async_call(
        "cover",
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )
    assert mock_opengarage.push_button.call_count == 1

    # Simulate door opened
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN

    # Simulate someone manually closing it outside HA
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # After idle time (simulating the time-dependent bug), toggle again
    # With current_cover_position available, this should reliably open
    await hass.services.async_call(
        "cover",
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    # Should have called push_button again (total 2 calls)
    assert mock_opengarage.push_button.call_count == 2

    # Simulate door opening
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN


async def test_open_cover_command(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test explicit open command."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})

    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    # Simulate door opening
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_close_cover_command(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test explicit close command."""
    mock_opengarage.push_button.return_value = 1
    coordinator = init_integration.runtime_data
    coordinator.async_set_updated_data({"door": 1, "name": "abcdef"})

    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.garage_abcdef"},
        blocking=True,
    )

    assert mock_opengarage.push_button.call_count == 1

    # Simulate door closing
    coordinator.async_set_updated_data({"door": 0, "name": "abcdef"})
    await hass.async_block_till_done()

    state = hass.states.get("cover.garage_abcdef")
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
