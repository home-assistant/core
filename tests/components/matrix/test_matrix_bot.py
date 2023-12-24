"""Configure and test MatrixBot."""
from functools import partial
from typing import Any

from nio import MatrixRoom, RoomMessageText
from pydantic.dataclasses import dataclass
import pytest

from homeassistant.components.matrix import (
    DOMAIN as MATRIX_DOMAIN,
    SERVICE_SEND_MESSAGE,
    MatrixBot,
    RoomID,
)
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import Event, HomeAssistant

from .conftest import (
    MOCK_EXPRESSION_COMMANDS,
    MOCK_WORD_COMMANDS,
    TEST_NOTIFIER_NAME,
    TEST_ROOM_A_ID,
    TEST_ROOM_B_ID,
    TEST_ROOM_C_ID,
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


@dataclass
class CommandTestParameters:
    """Dataclass of parameters representing the command config parameters and expected result state."""

    room_id: RoomID
    room_message: RoomMessageText
    expected_event_data_extra: dict[str, Any] | None

    @property
    def expected_event_data(self) -> dict[str, Any] | None:
        """Fully-constructed expected event data."""
        if self.expected_event_data_extra is not None:
            return {
                "sender": "@SomeUser:example.com",
                "room": self.room_id,
            } | self.expected_event_data_extra
        else:
            return None


room_message_base = partial(
    RoomMessageText,
    formatted_body=None,
    format=None,
    source={
        "event_id": "fake_event_id",
        "sender": "@SomeUser:example.com",
        "origin_server_ts": 123456789,
    },
)

word_command_global = partial(
    CommandTestParameters,
    room_message=room_message_base(body="!WordTrigger arg1 arg2"),
    expected_event_data_extra={
        "command": "WordTriggerEventName",
        "args": ["arg1", "arg2"],
    },
)

expr_command_global = partial(
    CommandTestParameters,
    room_message=room_message_base(body="My name is FakeName"),
    expected_event_data_extra={
        "command": "ExpressionTriggerEventName",
        "args": {"name": "FakeName"},
    },
)

word_command_subset = partial(
    CommandTestParameters,
    room_message=room_message_base(body="!WordTriggerSubset arg1 arg2"),
    expected_event_data_extra={
        "command": "WordTriggerSubsetEventName",
        "args": ["arg1", "arg2"],
    },
)

expr_command_subset = partial(
    CommandTestParameters,
    room_message=room_message_base(body="Your name is FakeName"),
    expected_event_data_extra={
        "command": "ExpressionTriggerSubsetEventName",
        "args": {"name": "FakeName"},
    },
)


@pytest.mark.parametrize(
    "params",
    [
        word_command_global(room_id=TEST_ROOM_A_ID),
        word_command_global(room_id=TEST_ROOM_B_ID),
        word_command_global(room_id=TEST_ROOM_C_ID),
        expr_command_global(room_id=TEST_ROOM_A_ID),
        expr_command_global(room_id=TEST_ROOM_B_ID),
        expr_command_global(room_id=TEST_ROOM_C_ID),
        word_command_subset(room_id=TEST_ROOM_A_ID, expected_event_data_extra=None),
        word_command_subset(room_id=TEST_ROOM_B_ID),
        word_command_subset(room_id=TEST_ROOM_C_ID),
        expr_command_subset(room_id=TEST_ROOM_A_ID, expected_event_data_extra=None),
        expr_command_subset(room_id=TEST_ROOM_B_ID),
        expr_command_subset(room_id=TEST_ROOM_C_ID),
    ],
)
async def test_commands(
    hass: HomeAssistant, matrix_bot: MatrixBot, command_events, params
):
    """Test that the configured commands were parsed and used correctly."""
    await hass.async_start()
    assert len(command_events) == 0

    assert matrix_bot._word_commands == MOCK_WORD_COMMANDS
    assert matrix_bot._expression_commands == MOCK_EXPRESSION_COMMANDS

    room = MatrixRoom(room_id=params.room_id, own_user_id=matrix_bot._mx_id)
    await matrix_bot._handle_room_message(room, params.room_message)
    await hass.async_block_till_done()
    match command_events:
        case [Event() as event] if params.expected_event_data is not None:
            assert event.data == params.expected_event_data
        case [] if params.expected_event_data is None:
            pass
        case _:
            pytest.fail(f"Unexpected data in {command_events=}")
