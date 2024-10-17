"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, Mock

from freezegun.api import FrozenDateTimeFactory
from homeconnect.api import HomeConnectAPI
import pytest

from homeassistant.components.home_connect.const import (
    BSH_EVENT_PRESENT_STATE_CONFIRMED,
    BSH_EVENT_PRESENT_STATE_OFF,
    BSH_EVENT_PRESENT_STATE_PRESENT,
    COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
    REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HC_APP = "Dishwasher"


EVENT_PROG_DELAYED_START = {
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.DelayedStart"
    },
}

EVENT_PROG_REMAIN_NO_VALUE = {
    "BSH.Common.Option.RemainingProgramTime": {},
    "BSH.Common.Status.OperationState": {
        "value": "BSH.Common.EnumType.OperationState.DelayedStart"
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


@pytest.mark.usefixtures("bypass_throttle")
async def test_sensors(
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
    EVENT_PROG_RUN,
    EVENT_PROG_UPDATE_1,
    EVENT_PROG_UPDATE_2,
    EVENT_PROG_END,
)

# Entity mapping to expected state at each program sequence.
ENTITY_ID_STATES = {
    "sensor.dishwasher_operation_state": (
        "delayedstart",
        "run",
        "run",
        "run",
        "ready",
    ),
    "sensor.dishwasher_program_finish_time": (
        "unavailable",
        "2021-01-09T12:00:00+00:00",
        "2021-01-09T12:00:00+00:00",
        "2021-01-09T12:00:20+00:00",
        "unavailable",
    ),
    "sensor.dishwasher_program_progress": (
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
    list(
        zip(
            list(zip(*ENTITY_ID_STATES.values(), strict=False)),
            PROGRAM_SEQUENCE_EVENTS,
            strict=False,
        )
    ),
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_event_sensors(
    appliance: Mock,
    states: tuple,
    event_run: dict,
    freezer: FrozenDateTimeFactory,
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
    appliance.get_programs_available = MagicMock(return_value=["dummy_program"])
    appliance.status.update(EVENT_PROG_DELAYED_START)
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    appliance.status.update(event_run)
    for entity_id, state in zip(entity_ids, states, strict=False):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
        assert hass.states.is_state(entity_id, state)


# Program sequence for SensorDeviceClass.TIMESTAMP edge cases.
PROGRAM_SEQUENCE_EDGE_CASE = [
    EVENT_PROG_REMAIN_NO_VALUE,
    EVENT_PROG_RUN,
    EVENT_PROG_END,
    EVENT_PROG_END,
]

# Expected state at each sequence.
ENTITY_ID_EDGE_CASE_STATES = [
    "unavailable",
    "2021-01-09T12:00:01+00:00",
    "unavailable",
    "unavailable",
]


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
@pytest.mark.usefixtures("bypass_throttle")
async def test_remaining_prog_time_edge_cases(
    appliance: Mock,
    freezer: FrozenDateTimeFactory,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Run program sequence to test edge cases for the remaining_prog_time entity."""
    get_appliances.return_value = [appliance]
    entity_id = "sensor.dishwasher_program_finish_time"
    time_to_freeze = "2021-01-09 12:00:00+00:00"
    freezer.move_to(time_to_freeze)

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.get_programs_available = MagicMock(return_value=["dummy_program"])
    appliance.status.update(EVENT_PROG_REMAIN_NO_VALUE)
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    for (
        event,
        expected_state,
    ) in zip(PROGRAM_SEQUENCE_EDGE_CASE, ENTITY_ID_EDGE_CASE_STATES, strict=False):
        appliance.status.update(event)
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
        freezer.tick()
        assert hass.states.is_state(entity_id, expected_state)


@pytest.mark.parametrize(
    ("entity_id", "status_key", "event_value_update", "expected", "appliance"),
    [
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            "EVENT_NOT_IN_STATUS_YET_SO_SET_TO_OFF",
            "",
            "off",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
            BSH_EVENT_PRESENT_STATE_OFF,
            "off",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
            BSH_EVENT_PRESENT_STATE_PRESENT,
            "present",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
            BSH_EVENT_PRESENT_STATE_CONFIRMED,
            "confirmed",
            "FridgeFreezer",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            "EVENT_NOT_IN_STATUS_YET_SO_SET_TO_OFF",
            "",
            "off",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
            BSH_EVENT_PRESENT_STATE_OFF,
            "off",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
            BSH_EVENT_PRESENT_STATE_PRESENT,
            "present",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
            BSH_EVENT_PRESENT_STATE_CONFIRMED,
            "confirmed",
            "CoffeeMaker",
        ),
    ],
    indirect=["appliance"],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_sensors_states(
    entity_id: str,
    status_key: str,
    event_value_update: str,
    appliance: Mock,
    expected: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Tests for Appliance alarm sensors."""
    appliance.status.update(
        HomeConnectAPI.json2dict(
            load_json_object_fixture("home_connect/status.json")["data"]["status"]
        )
    )
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    appliance.status.update({status_key: {"value": event_value_update}})
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)
