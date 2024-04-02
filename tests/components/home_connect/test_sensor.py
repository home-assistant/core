"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from unittest.mock import MagicMock

from dateutil.parser import parse
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
    bypass_throttle,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance,
) -> None:
    """Test sensor entities."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
async def test_event_sensors(
    appliance,
    bypass_throttle,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Tests for sensors that are only available after an event happens."""
    EVENT_RUN = (
        EVENT_PROG_DELAYED_START,
        EVENT_PROG_REMAIN_NO_VALUE,
        EVENT_PROG_RUN,
        EVENT_PROG_UPDATE_1,
        EVENT_PROG_UPDATE_2,
        EVENT_PROG_END,
    )

    ENTITY_ID_STATES = [
        (
            "sensor.dishwasher_operation_state",
            ["Delayed", "Delayed", "Run", "Run", "Run", "Ready"],
        ),
        (
            "sensor.dishwasher_remaining_program_time",
            [],
        ),
        (
            "sensor.dishwasher_program_progress",
            [
                "unavailable",
                "unavailable",
                "60",
                "80",
                "99",
                "99",
            ],
        ),
    ]
    appliance.status.update(EVENT_PROG_END)

    get_appliances.return_value = [appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert hass.states.is_state(
        "sensor.dishwasher_remaining_program_time", "unavailable"
    )

    for count, event in enumerate(EVENT_RUN):
        appliance.status.update(event)
        for entity_id, states in ENTITY_ID_STATES:
            await async_update_entity(hass, entity_id)
            await hass.async_block_till_done()
            # Check to see if sensor is unavailable or a datetime object.
            if entity_id == "sensor.dishwasher_remaining_program_time":
                prog_state = hass.states.get(entity_id)
                assert prog_state.state == "unavailable" or isinstance(
                    parse(prog_state.state), datetime
                )
            else:
                assert hass.states.is_state(entity_id, states[count])

        states = hass.states.async_all()
        await hass.async_block_till_done()
        type(states)
