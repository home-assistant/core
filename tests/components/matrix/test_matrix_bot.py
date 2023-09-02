"""Configure and test MatrixBot."""
from nio import MatrixRoom, RoomMessageText

from homeassistant.components.matrix import (
    DOMAIN as MATRIX_DOMAIN,
    SERVICE_SEND_MESSAGE,
    MatrixBot,
)
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_EXPRESSION_COMMANDS,
    MOCK_WORD_COMMANDS,
    TEST_JOINABLE_ROOMS,
    TEST_NOTIFIER_NAME,
)


async def test_services(hass: HomeAssistant, matrix_bot: MatrixBot):
    """Test hass/MatrixBot state."""

    services = hass.services.async_services()

    # Verify that the matrix service is registered
    assert (matrix_service := services.get(MATRIX_DOMAIN))
    assert SERVICE_SEND_MESSAGE in matrix_service

    # Verify that the matrix notifier is registered
    assert (notify_service := services.get(NOTIFY_DOMAIN))
    assert TEST_NOTIFIER_NAME in notify_service


async def test_commands(hass, matrix_bot: MatrixBot, command_events):
    """Test that the configured commands were parsed correctly."""

    assert len(command_events) == 0

    assert matrix_bot._word_commands == MOCK_WORD_COMMANDS
    assert matrix_bot._expression_commands == MOCK_EXPRESSION_COMMANDS

    room_id = TEST_JOINABLE_ROOMS[0]
    room = MatrixRoom(room_id=room_id, own_user_id=matrix_bot._mx_id)

    # Test single-word command.
    word_command_message = RoomMessageText(
        body="!WordTrigger arg1 arg2",
        formatted_body=None,
        format=None,
        source={
            "event_id": "fake_event_id",
            "sender": "@SomeUser:example.com",
            "origin_server_ts": 123456789,
        },
    )
    await matrix_bot._handle_room_message(room, word_command_message)
    await hass.async_block_till_done()
    assert len(command_events) == 1
    event = command_events.pop()
    assert event.data == {
        "command": "WordTriggerEventName",
        "sender": "@SomeUser:example.com",
        "room": room_id,
        "args": ["arg1", "arg2"],
    }

    # Test expression command.
    room = MatrixRoom(room_id=room_id, own_user_id=matrix_bot._mx_id)
    expression_command_message = RoomMessageText(
        body="My name is FakeName",
        formatted_body=None,
        format=None,
        source={
            "event_id": "fake_event_id",
            "sender": "@SomeUser:example.com",
            "origin_server_ts": 123456789,
        },
    )
    await matrix_bot._handle_room_message(room, expression_command_message)
    await hass.async_block_till_done()
    assert len(command_events) == 1
    event = command_events.pop()
    assert event.data == {
        "command": "ExpressionTriggerEventName",
        "sender": "@SomeUser:example.com",
        "room": room_id,
        "args": {"name": "FakeName"},
    }
