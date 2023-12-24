"""Test MatrixBot's ability to parse and respond to commands in matrix rooms."""

from functools import partial
from typing import Any

from nio import MatrixRoom, RoomMessageText
from pydantic.dataclasses import dataclass
import pytest

from homeassistant.components.matrix import MatrixBot, RoomID
from homeassistant.core import Event, HomeAssistant

from tests.components.matrix.conftest import (
    MOCK_EXPRESSION_COMMANDS,
    MOCK_WORD_COMMANDS,
    TEST_MXID,
    TEST_ROOM_A_ID,
    TEST_ROOM_B_ID,
    TEST_ROOM_C_ID,
)


@dataclass
class CommandTestParameters:
    """Dataclass of parameters representing the command config parameters and expected result state."""

    room_id: RoomID
    room_message: RoomMessageText
    expected_event_data_extra: dict[str, Any] | None

    @property
    def expected_event_data(self) -> dict[str, Any] | None:
        """Fully-constructed expected event data.

        Commands that are named with 'Subset' are expected not to be read from Room A.
        """

        if (
            self.expected_event_data_extra is None
            or "Subset" in self.expected_event_data_extra["command"]
            and self.room_id == TEST_ROOM_A_ID
        ):
            return None
        return {
            "sender": "@SomeUser:example.com",
            "room": self.room_id,
        } | self.expected_event_data_extra


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
# Messages without commands should trigger nothing
fake_command_global = partial(
    CommandTestParameters,
    room_message=room_message_base(body="This is not a real command!"),
    expected_event_data_extra=None,
)
# Valid commands sent by the bot user should trigger nothing
self_command_global = partial(
    CommandTestParameters,
    room_message=room_message_base(
        body="!WordTrigger arg1 arg2",
        source={
            "event_id": "fake_event_id",
            "sender": TEST_MXID,
            "origin_server_ts": 123456789,
        },
    ),
    expected_event_data_extra=None,
)


@pytest.mark.parametrize("room_id", [TEST_ROOM_A_ID, TEST_ROOM_B_ID, TEST_ROOM_C_ID])
@pytest.mark.parametrize(
    "partial_param",
    [
        word_command_global,
        expr_command_global,
        word_command_subset,
        expr_command_subset,
        fake_command_global,
        self_command_global,
    ],
)
async def test_commands(
    hass: HomeAssistant, matrix_bot: MatrixBot, command_events, partial_param, room_id
):
    """Test that the configured commands were parsed and used correctly."""
    await hass.async_start()
    assert len(command_events) == 0

    assert matrix_bot._word_commands == MOCK_WORD_COMMANDS
    assert matrix_bot._expression_commands == MOCK_EXPRESSION_COMMANDS

    command_param: CommandTestParameters = partial_param(room_id=room_id)

    room = MatrixRoom(room_id=command_param.room_id, own_user_id=matrix_bot._mx_id)
    await matrix_bot._handle_room_message(room, command_param.room_message)
    await hass.async_block_till_done()
    match command_events:
        case [Event() as event] if command_param.expected_event_data is not None:
            assert event.data == command_param.expected_event_data
        case [] if command_param.expected_event_data is None:
            pass
        case _:
            pytest.fail(f"Unexpected data in {command_events=}")
