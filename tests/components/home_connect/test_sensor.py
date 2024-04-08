"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable, Generator
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, Mock

from dateutil.parser import parse
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

TEST_HC_APP = "Dishwasher"


EVENT_PROG_DELAYED_START = {
    "BSH.Common.Option.RemainingProgramTime": {},
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.Delayed"
    },
}

EVENT_PROG_REMAIN_NO_VALUE = {
    "BSH.Common.Option.RemainingProgramTime": {},
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.Delayed"
    },
}


EVENT_PROG_RUN = {
    "BSH.Common.Option.RemainingProgramTime": {"value": "0"},
    "BSH.Common.Option.ProgramProgress": {"value": "60"},
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.Run"
    },
}


EVENT_PROG_UPDATE_1 = {
    "BSH.Common.Option.RemainingProgramTime": {"value": "0"},
    "BSH.Common.Option.ProgramProgress": {"value": "80"},
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.Run"
    },
}

EVENT_PROG_UPDATE_2 = {
    "BSH.Common.Option.RemainingProgramTime": {"value": "20"},
    "BSH.Common.Option.ProgramProgress": {"value": "99"},
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.Run"
    },
}

EVENT_PROG_END = {
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.Ready"
    },
}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def test_sensors(
    bypass_throttle: Generator[None, Any, None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Test sensor entities."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


# Appliance program sequence with a delayed start.
PROGRAM_SEQUENCE_EVENTS = (
    EVENT_PROG_DELAYED_START,
    EVENT_PROG_REMAIN_NO_VALUE,
    EVENT_PROG_RUN,
    EVENT_PROG_UPDATE_1,
    EVENT_PROG_UPDATE_2,
    EVENT_PROG_END,
)

# Entity mapping to expected state at each program sequence.
ENTITY_ID_STATES = {
    "sensor.dishwasher_operation_state": (
        "Delayed",
        "Delayed",
        "Run",
        "Run",
        "Run",
        "Ready",
    ),
    "sensor.dishwasher_remaining_program_time": (
        "unavailable",
        "unavailable",
        "2021-01-09T12:00:00+00:00",
        "2021-01-09T12:00:00+00:00",
        "2021-01-09T12:00:20+00:00",
        "unavailable",
    ),
    "sensor.dishwasher_program_progress": (
        "unavailable",
        "unavailable",
        "60",
        "80",
        "99",
        "unavailable",
    ),
}


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
@pytest.mark.parametrize(
    ("states", "event_run"),
    list(zip(list(zip(*ENTITY_ID_STATES.values())), PROGRAM_SEQUENCE_EVENTS)),
)
async def test_event_sensors(
    appliance: Mock,
    states: tuple,
    event_run: dict,
    freezer: FrozenDateTimeFactory,
    bypass_throttle: Generator[None, Any, None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test sequence for sensors that are only available after an event happens."""
    entity_ids = ENTITY_ID_STATES.keys()

    time_to_freeze = "2021-01-09 12:00:00+00:00"
    freezer.move_to(time_to_freeze)

    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(event_run)
    for entity_id, state in zip(entity_ids, states):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
        assert hass.states.is_state(entity_id, state)


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
async def test_remaining_prog_time_edge_cases(
    appliance,
    bypass_throttle,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Run program sequence to test edge cases for the remaining_prog_time entity."""
    get_appliances.return_value = [appliance]
    entity_id = "sensor.dishwasher_remaining_program_time"

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    for event, state in zip(PROGRAM_SEQUENCE_EVENTS, ENTITY_ID_STATES[entity_id]):
        appliance.status.update(event)
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == "unavailable" or isinstance(parse(state.state), datetime)
