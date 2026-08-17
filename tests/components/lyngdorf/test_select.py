"""Tests for the Lyngdorf select platform."""

from unittest.mock import MagicMock

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ROOM_PERFECT_ENTITY_ID = "select.mock_lyngdorf_roomperfect_position"
VOICING_ENTITY_ID = "select.mock_lyngdorf_voicing"


async def test_select_entities_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test that select entities are created."""
    assert init_integration.state.value == "loaded"
    assert hass.states.get(ROOM_PERFECT_ENTITY_ID) is not None
    assert hass.states.get(VOICING_ENTITY_ID) is not None


async def test_room_perfect_current_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test that the RoomPerfect select entity reflects the current position."""
    mock_receiver.room_perfect_position = "focus"
    mock_receiver.available_room_perfect_positions = ["focus", "global"]

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ROOM_PERFECT_ENTITY_ID)
    assert state is not None
    assert state.state == "focus"


async def test_room_perfect_select_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting a RoomPerfect position."""
    mock_receiver.room_perfect_position = "focus"
    mock_receiver.available_room_perfect_positions = ["focus", "global"]

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: ROOM_PERFECT_ENTITY_ID,
            "option": "global",
        },
        blocking=True,
    )

    assert mock_receiver.room_perfect_position == "global"


async def test_voicing_current_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test that the voicing select entity reflects the current voicing."""
    mock_receiver.voicing = "Neutral"
    mock_receiver.available_voicings = ["Neutral", "Music", "Movie"]

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(VOICING_ENTITY_ID)
    assert state is not None
    assert state.state == "Neutral"


async def test_voicing_select_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting a voicing."""
    mock_receiver.voicing = "Neutral"
    mock_receiver.available_voicings = ["Neutral", "Music", "Movie"]

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: VOICING_ENTITY_ID,
            "option": "Movie",
        },
        blocking=True,
    )

    assert mock_receiver.voicing == "Movie"
