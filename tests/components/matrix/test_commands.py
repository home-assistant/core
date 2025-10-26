"""Test MatrixBot's ability to parse and respond to commands in matrix rooms."""

from dataclasses import dataclass
from functools import partial
from itertools import chain
from typing import Any

from nio import MatrixRoom, RoomMessageText
import pytest

from homeassistant.components.matrix import MatrixBot, RoomID
from homeassistant.core import Event, HomeAssistant

from .conftest import (
    MOCK_EXPRESSION_COMMANDS,
    MOCK_WORD_COMMANDS,
    TEST_MXID,
    TEST_ROOM_A_ID,
    TEST_ROOM_B_ID,
    TEST_ROOM_C_ID,
)

ALL_ROOMS = (TEST_ROOM_A_ID, TEST_ROOM_B_ID, TEST_ROOM_C_ID)
SUBSET_ROOMS = (TEST_ROOM_B_ID, TEST_ROOM_C_ID)


@dataclass
class CommandTestParameters:
    """Dataclass of parameters representing the command config parameters and expected result state.

    Switches behavior based on `room_id` and `expected_event_room_data`.
    """

    room_id: RoomID
    room_message: RoomMessageText
    expected_event_data_extra: dict[str, Any] | None

    @property
    def expected_event_data(self) -> dict[str, Any] | None:
        """Fully-constructed expected event data.

        Commands that are named with 'Subset' are expected not to be read from Room A.
        """

        if self.expected_event_data_extra is None or (
            "Subset" in self.expected_event_data_extra["command"]
            and self.room_id not in SUBSET_ROOMS
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


@pytest.mark.parametrize(
    "command_params",
    chain(
        (word_command_global(room_id) for room_id in ALL_ROOMS),
        (expr_command_global(room_id) for room_id in ALL_ROOMS),
        (word_command_subset(room_id) for room_id in SUBSET_ROOMS),
        (expr_command_subset(room_id) for room_id in SUBSET_ROOMS),
    ),
)
async def test_commands(
    hass: HomeAssistant,
    matrix_bot: MatrixBot,
    command_events: list[Event],
    command_params: CommandTestParameters,
) -> None:
    """Test that the configured commands are used correctly."""
    room = MatrixRoom(room_id=command_params.room_id, own_user_id=matrix_bot._mx_id)

    await hass.async_start()
    assert len(command_events) == 0
    await matrix_bot._handle_room_message(room, command_params.room_message)
    await hass.async_block_till_done()

    # MatrixBot should emit exactly one Event with matching data from this Command
    assert len(command_events) == 1
    event = command_events[0]
    assert event.data == command_params.expected_event_data


@pytest.mark.parametrize(
    "command_params",
    chain(
        (word_command_subset(TEST_ROOM_A_ID),),
        (expr_command_subset(TEST_ROOM_A_ID),),
        (fake_command_global(room_id) for room_id in ALL_ROOMS),
        (self_command_global(room_id) for room_id in ALL_ROOMS),
    ),
)
async def test_non_commands(
    hass: HomeAssistant,
    matrix_bot: MatrixBot,
    command_events: list[Event],
    command_params: CommandTestParameters,
) -> None:
    """Test that normal/non-qualifying messages don't wrongly trigger commands."""
    room = MatrixRoom(room_id=command_params.room_id, own_user_id=matrix_bot._mx_id)

    await hass.async_start()
    assert len(command_events) == 0
    await matrix_bot._handle_room_message(room, command_params.room_message)
    await hass.async_block_till_done()

    # MatrixBot should not treat this message as a Command
    assert len(command_events) == 0


async def test_commands_parsing(hass: HomeAssistant, matrix_bot: MatrixBot) -> None:
    """Test that the configured commands were parsed correctly."""

    await hass.async_start()
    assert matrix_bot._word_commands == MOCK_WORD_COMMANDS
    assert matrix_bot._expression_commands == MOCK_EXPRESSION_COMMANDS
