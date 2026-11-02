"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfStatus,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
    Status,
    StatusKey,
)
from aiohomeconnect.model.error import HomeConnectApiError, TooManyRequestsError
from aiohomeconnect.model.program import (
    ArrayOfPrograms,
    EnumerateProgram,
    Option,
    OptionKey,
    Program,
    ProgramKey,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.home_connect.const import (
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    BSH_EVENT_PRESENT_STATE_CONFIRMED,
    BSH_EVENT_PRESENT_STATE_OFF,
    BSH_EVENT_PRESENT_STATE_PRESENT,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_READY,
    BSH_OPERATION_STATE_RUN,
    DOMAIN,
)
from homeassistant.components.home_connect.coordinator import HomeConnectError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import (
    Event as HassEvent,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from . import create_event_message, create_operation_state_status

TEST_HC_APP = "Dishwasher"


EVENT_PROG_DELAYED_START = {
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
            "BSH.Common.EnumType.OperationState.DelayedStart"
        ),
    },
    EventType.EVENT: {
        EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 30,
        EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 0,
    },
}


EVENT_PROG_RUN = {
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
            "BSH.Common.EnumType.OperationState.Run"
        ),
    },
    EventType.EVENT: {
        EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 0,
        EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 60,
    },
}

EVENT_PROG_UPDATE_1 = {
    EventType.EVENT: {
        EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 0,
        EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 80,
    },
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
            "BSH.Common.EnumType.OperationState.Run"
        ),
    },
}

EVENT_PROG_UPDATE_2 = {
    EventType.EVENT: {
        EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 20,
        EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 99,
    },
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
            "BSH.Common.EnumType.OperationState.Run"
        ),
    },
}


EVENT_PROG_UPDATE_3 = {
    EventType.EVENT: {
        EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: None,
        EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 99,
    },
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
            "BSH.Common.EnumType.OperationState.Run"
        ),
    },
}

EVENT_PROG_END = {
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
            "BSH.Common.EnumType.OperationState.Ready"
        ),
    },
}


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test device removal and re-addition on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize(
    ("appliance", "keys_to_check"),
    [
        (
            "Washer",
            (StatusKey.BSH_COMMON_OPERATION_STATE,),
        )
    ],
    indirect=["appliance"],
)
async def test_connected_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    keys_to_check: tuple,
) -> None:
    """Test that devices reconnected.

    Specifically those devices whose settings, status, etc. could
    not be obtained while disconnected and once connected, the entities are added.
    """
    get_status_original_mock = client.get_status

    def get_status_side_effect(ha_id: str):
        if ha_id == appliance.ha_id:
            raise HomeConnectApiError(
                "SDK.Error.HomeAppliance.Connection.Initialization.Failed"
            )
        return get_status_original_mock.return_value

    client.get_status = AsyncMock(side_effect=get_status_side_effect)
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_status = get_status_original_mock

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert device
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.SENSOR,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for key in keys_to_check:
        assert entity_registry.async_get_entity_id(
            Platform.SENSOR,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
async def test_sensor_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test sensor entities availability based on appliance connection."""
    entity_ids = [
        "sensor.dishwasher_operation_state",
        "sensor.dishwasher_salt_nearly_empty",
    ]
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE


# Appliance program sequence with a delayed start.
PROGRAM_SEQUENCE_EVENTS = (
    EVENT_PROG_DELAYED_START,
    EVENT_PROG_RUN,
    EVENT_PROG_UPDATE_1,
    EVENT_PROG_UPDATE_2,
    EVENT_PROG_UPDATE_3,
    EVENT_PROG_END,
)

# Entity mapping to expected state at each program sequence.
ENTITY_ID_STATES = {
    "sensor.dishwasher_operation_state": (
        "delayedstart",
        "run",
        "run",
        "run",
        "run",
        "ready",
    ),
    "sensor.dishwasher_program_finish_time": (
        "2021-01-09T12:00:30+00:00",
        "2021-01-09T12:00:00+00:00",
        "2021-01-09T12:00:00+00:00",
        "2021-01-09T12:00:20+00:00",
        STATE_UNKNOWN,
        STATE_UNAVAILABLE,
    ),
    "sensor.dishwasher_program_progress": (
        "0",
        "60",
        "80",
        "99",
        "99",
        STATE_UNAVAILABLE,
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
async def test_program_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    states: tuple,
    event_run: dict[EventType, dict[EventKey, str | int]],
) -> None:
    """Test sequence for sensors that expose information about a program."""
    entity_ids = ENTITY_ID_STATES.keys()

    time_to_freeze = "2021-01-09 12:00:00+00:00"
    freezer.move_to(time_to_freeze)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    client.get_status.return_value.status.extend(
        Status(
            key=StatusKey(event_key.value),
            raw_key=event_key.value,
            value=value,
        )
        for event_key, value in EVENT_PROG_DELAYED_START[EventType.STATUS].items()
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                event_type,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=value,
                        )
                    ],
                ),
            )
            for event_type, events in event_run.items()
            for event_key, value in events.items()
        ]
    )
    await hass.async_block_till_done()
    for entity_id, state in zip(entity_ids, states, strict=False):
        assert hass.states.is_state(entity_id, state)


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
@pytest.mark.parametrize(
    ("initial_operation_state", "initial_state", "event_order", "entity_states"),
    [
        (
            "BSH.Common.EnumType.OperationState.Ready",
            STATE_UNAVAILABLE,
            (EventType.STATUS, EventType.EVENT),
            (STATE_UNKNOWN, "60"),
        ),
        (
            "BSH.Common.EnumType.OperationState.Run",
            STATE_UNKNOWN,
            (EventType.EVENT, EventType.STATUS),
            ("60", "60"),
        ),
    ],
)
async def test_program_sensor_edge_case(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    initial_operation_state: str,
    initial_state: str,
    event_order: tuple[EventType, EventType],
    entity_states: tuple[str, str],
    appliance: HomeAppliance,
) -> None:
    """Test edge case for the program related entities."""
    entity_id = "sensor.dishwasher_program_progress"
    client.get_status = AsyncMock(
        return_value=ArrayOfStatus(
            [
                Status(
                    StatusKey.BSH_COMMON_OPERATION_STATE,
                    StatusKey.BSH_COMMON_OPERATION_STATE.value,
                    initial_operation_state,
                )
            ]
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, initial_state)

    for event_type, state in zip(event_order, entity_states, strict=True):
        await client.add_events(
            [
                EventMessage(
                    appliance.ha_id,
                    event_type,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=event_key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=value,
                            )
                        ],
                    ),
                )
                for event_key, value in EVENT_PROG_RUN[event_type].items()
            ]
        )
        await hass.async_block_till_done()
        assert hass.states.is_state(entity_id, state)


# Program sequence for SensorDeviceClass.TIMESTAMP edge cases.
PROGRAM_SEQUENCE_EDGE_CASE = [
    EVENT_PROG_DELAYED_START,
    EVENT_PROG_RUN,
    EVENT_PROG_END,
    EVENT_PROG_END,
]

# Expected state at each sequence.
ENTITY_ID_EDGE_CASE_STATES = [
    "2021-01-09T12:00:30+00:00",
    "2021-01-09T12:00:01+00:00",
    STATE_UNAVAILABLE,
    STATE_UNAVAILABLE,
]


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
async def test_remaining_prog_time_edge_cases(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Run program sequence to test edge cases for the remaining_prog_time entity."""
    entity_id = "sensor.dishwasher_program_finish_time"
    time_to_freeze = "2021-01-09 12:00:00+00:00"
    freezer.move_to(time_to_freeze)

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    for (
        event,
        expected_state,
    ) in zip(PROGRAM_SEQUENCE_EDGE_CASE, ENTITY_ID_EDGE_CASE_STATES, strict=False):
        await client.add_events(
            [
                EventMessage(
                    appliance.ha_id,
                    event_type,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=event_key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=value,
                            )
                        ],
                    ),
                )
                for event_type, events in event.items()
                for event_key, value in events.items()
            ]
        )
        await hass.async_block_till_done()
        freezer.tick()
        assert hass.states.is_state(entity_id, expected_state)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "entity_id",
        "event_key",
        "event_type",
        "event_value_update",
        "expected",
        "appliance",
    ),
    [
        (
            "sensor.dishwasher_door",
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            EventType.STATUS,
            BSH_DOOR_STATE_LOCKED,
            "locked",
            "Dishwasher",
        ),
        (
            "sensor.dishwasher_door",
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            EventType.STATUS,
            BSH_DOOR_STATE_CLOSED,
            "closed",
            "Dishwasher",
        ),
        (
            "sensor.dishwasher_door",
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            EventType.STATUS,
            BSH_DOOR_STATE_OPEN,
            "open",
            "Dishwasher",
        ),
        (
            "sensor.dishwasher_door",
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            EventType.STATUS,
            None,
            STATE_UNKNOWN,
            "Dishwasher",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            "EVENT_NOT_IN_STATUS_YET_SO_SET_TO_OFF",
            EventType.EVENT,
            "",
            "off",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
            EventType.EVENT,
            BSH_EVENT_PRESENT_STATE_OFF,
            "off",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
            EventType.EVENT,
            BSH_EVENT_PRESENT_STATE_PRESENT,
            "present",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
            EventType.EVENT,
            BSH_EVENT_PRESENT_STATE_CONFIRMED,
            "confirmed",
            "FridgeFreezer",
        ),
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
            EventType.EVENT,
            None,
            STATE_UNKNOWN,
            "FridgeFreezer",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            EventType.EVENT,
            "EVENT_NOT_IN_STATUS_YET_SO_SET_TO_OFF",
            "",
            "off",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
            EventType.EVENT,
            BSH_EVENT_PRESENT_STATE_OFF,
            "off",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
            EventType.EVENT,
            BSH_EVENT_PRESENT_STATE_PRESENT,
            "present",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
            EventType.EVENT,
            BSH_EVENT_PRESENT_STATE_CONFIRMED,
            "confirmed",
            "CoffeeMaker",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
            EventType.EVENT,
            None,
            STATE_UNKNOWN,
            "CoffeeMaker",
        ),
    ],
    indirect=["appliance"],
)
async def test_sensors_states(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_id: str,
    event_key: EventKey,
    event_type: EventType,
    event_value_update: str | None,
    appliance: HomeAppliance,
    expected: str,
) -> None:
    """Tests for appliance alarm sensors."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                event_type,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=str(event_key),
                            timestamp=0,
                            level="",
                            handling="",
                            value=event_value_update,
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.parametrize(
    (
        "appliance",
        "entity_id",
        "status_key",
        "unit_get_status",
        "unit_get_status_value",
        "get_status_value_call_count",
    ),
    [
        (
            "Oven",
            "sensor.oven_current_oven_cavity_temperature",
            StatusKey.COOKING_OVEN_CURRENT_CAVITY_TEMPERATURE,
            "°C",
            None,
            0,
        ),
        (
            "Oven",
            "sensor.oven_current_oven_cavity_temperature",
            StatusKey.COOKING_OVEN_CURRENT_CAVITY_TEMPERATURE,
            None,
            "°C",
            1,
        ),
    ],
    indirect=["appliance"],
)
async def test_sensor_unit_fetching(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
    status_key: StatusKey,
    unit_get_status: str | None,
    unit_get_status_value: str | None,
    get_status_value_call_count: int,
) -> None:
    """Test that the sensor entities are capable of fetching units."""

    async def get_status_mock(ha_id: str) -> ArrayOfStatus:
        if ha_id != appliance.ha_id:
            return ArrayOfStatus([])
        return ArrayOfStatus(
            [
                Status(
                    key=status_key,
                    raw_key=status_key.value,
                    value=0,
                    unit=unit_get_status,
                )
            ]
        )

    client.get_status = AsyncMock(side_effect=get_status_mock)
    client.get_status_value = AsyncMock(
        return_value=Status(
            key=status_key,
            raw_key=status_key.value,
            value=0,
            unit=unit_get_status_value,
        )
    )

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert (
        entity_state.attributes["unit_of_measurement"] == unit_get_status
        or unit_get_status_value
    )

    assert client.get_status_value.call_count == get_status_value_call_count


@pytest.mark.parametrize(
    (
        "appliance",
        "entity_id",
        "status_key",
    ),
    [
        (
            "Oven",
            "sensor.oven_current_oven_cavity_temperature",
            StatusKey.COOKING_OVEN_CURRENT_CAVITY_TEMPERATURE,
        ),
    ],
    indirect=["appliance"],
)
async def test_sensor_unit_fetching_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
    status_key: StatusKey,
) -> None:
    """Test that the sensor entities are capable of fetching units."""

    async def get_status_mock(ha_id: str) -> ArrayOfStatus:
        if ha_id != appliance.ha_id:
            return ArrayOfStatus([])
        return ArrayOfStatus(
            [
                Status(
                    key=status_key,
                    raw_key=status_key.value,
                    value=0,
                )
            ]
        )

    client.get_status = AsyncMock(side_effect=get_status_mock)
    client.get_status_value = AsyncMock(side_effect=HomeConnectError())

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)


@pytest.mark.parametrize(
    (
        "appliance",
        "entity_id",
        "status_key",
        "unit",
    ),
    [
        (
            "Oven",
            "sensor.oven_current_oven_cavity_temperature",
            StatusKey.COOKING_OVEN_CURRENT_CAVITY_TEMPERATURE,
            "°C",
        ),
    ],
    indirect=["appliance"],
)
async def test_sensor_unit_fetching_after_rate_limit_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    entity_id: str,
    status_key: StatusKey,
    unit: str,
) -> None:
    """Test that the sensor entities are capable of fetching units."""

    async def get_status_mock(ha_id: str) -> ArrayOfStatus:
        if ha_id != appliance.ha_id:
            return ArrayOfStatus([])
        return ArrayOfStatus(
            [
                Status(
                    key=status_key,
                    raw_key=status_key.value,
                    value=0,
                )
            ]
        )

    client.get_status = AsyncMock(side_effect=get_status_mock)
    client.get_status_value = AsyncMock(
        side_effect=[
            TooManyRequestsError("error.key", retry_after=1),
            Status(
                key=status_key,
                raw_key=status_key.value,
                value=0,
                unit=unit,
            ),
        ]
    )

    assert await integration_setup(client)
    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)
    freezer.tick(1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert client.get_status_value.call_count == 2

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == "0"
    assert entity_state.attributes["unit_of_measurement"] == unit


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all sensor entities to fixate the full set and their attributes."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


OVEN_FINISH_TIME_ENTITY_ID = "sensor.oven_program_finish_time"
OVEN_PROGRESS_ENTITY_ID = "sensor.oven_program_progress"
OVEN_RUNNING_TIME_ENTITY_ID = "sensor.oven_program_running_time"
PROGRAM_TIMES_TEST_START = "2021-01-09 12:00:00+00:00"


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    "end_events",
    [
        pytest.param(
            [
                (EventType.NOTIFY, {EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: None}),
                (
                    EventType.STATUS,
                    {
                        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
                            BSH_OPERATION_STATE_READY
                        )
                    },
                ),
            ],
            id="active_program_cleared_then_ready",
        ),
        pytest.param(
            [
                (
                    EventType.STATUS,
                    {
                        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
                            BSH_OPERATION_STATE_READY
                        )
                    },
                ),
                (EventType.NOTIFY, {EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: None}),
            ],
            id="ready_then_active_program_cleared",
        ),
        pytest.param(
            [
                (
                    EventType.STATUS,
                    {
                        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
                            BSH_OPERATION_STATE_READY
                        )
                    },
                ),
            ],
            id="ready_only",
        ),
    ],
)
@pytest.mark.parametrize(
    "next_program",
    [
        ProgramKey.COOKING_OVEN_HEATING_MODE_HOT_AIR,
        ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING,
    ],
)
async def test_program_finish_time_not_carried_over_to_next_program(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    end_events: list[tuple[EventType, dict[EventKey, Any]]],
    next_program: ProgramKey,
) -> None:
    """Test a program without a timer doesn't show the previous remaining time."""
    freezer.move_to(PROGRAM_TIMES_TEST_START)
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_RUN)
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {
                    EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1800,
                    EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 10,
                },
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, "2021-01-09T12:30:00+00:00")
    assert hass.states.is_state(OVEN_PROGRESS_ENTITY_ID, "10")

    await client.add_events(
        [
            *(
                create_event_message(appliance.ha_id, event_type, items)
                for event_type, items in end_events
            ),
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: next_program.value},
            ),
            create_event_message(
                appliance.ha_id,
                EventType.STATUS,
                {EventKey.BSH_COMMON_STATUS_OPERATION_STATE: BSH_OPERATION_STATE_RUN},
            ),
            # The first event after a disconnection updates all the entities.
            EventMessage(appliance.ha_id, EventType.DISCONNECTED, ArrayOfEvents([])),
            create_event_message(
                appliance.ha_id,
                EventType.STATUS,
                {EventKey.BSH_COMMON_STATUS_OPERATION_STATE: BSH_OPERATION_STATE_RUN},
            ),
        ]
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, STATE_UNKNOWN)
    assert hass.states.is_state(OVEN_PROGRESS_ENTITY_ID, STATE_UNKNOWN)


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("program_change_items", "expected_finish_time", "expected_progress"),
    [
        pytest.param(
            {
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                    ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING.value
                )
            },
            STATE_UNKNOWN,
            STATE_UNKNOWN,
            id="new_program_without_timer",
        ),
        pytest.param(
            {
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                    ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING.value
                ),
                EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 600,
                EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 0,
            },
            "2021-01-09T12:10:00+00:00",
            "0",
            id="new_program_with_timer",
        ),
        pytest.param(
            {
                EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 600,
                EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 0,
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                    ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING.value
                ),
            },
            "2021-01-09T12:10:00+00:00",
            "0",
            id="new_program_with_timer_reported_before_program",
        ),
        pytest.param(
            {
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                    ProgramKey.COOKING_OVEN_HEATING_MODE_HOT_AIR.value
                )
            },
            "2021-01-09T12:30:00+00:00",
            "10",
            id="same_program",
        ),
    ],
)
async def test_program_finish_time_on_program_change_while_running(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    program_change_items: dict[EventKey, Any],
    expected_finish_time: str,
    expected_progress: str,
) -> None:
    """Test the progress of the previous program is dropped on a program change."""
    freezer.move_to(PROGRAM_TIMES_TEST_START)
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_RUN)
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {
                    EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1800,
                    EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 10,
                },
            ),
            create_event_message(
                appliance.ha_id, EventType.NOTIFY, program_change_items
            ),
        ]
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, expected_finish_time)
    assert hass.states.is_state(OVEN_PROGRESS_ENTITY_ID, expected_progress)


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("active_program_options", "expected_finish_time", "expected_progress"),
    [
        pytest.param([], STATE_UNKNOWN, STATE_UNKNOWN, id="without_timer"),
        pytest.param(
            [
                Option(OptionKey.BSH_COMMON_REMAINING_PROGRAM_TIME, 600),
                Option(OptionKey.BSH_COMMON_PROGRAM_PROGRESS, 50),
            ],
            "2021-01-09T12:10:00+00:00",
            "50",
            id="with_timer",
        ),
    ],
)
async def test_program_finish_time_after_reconnection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    active_program_options: list[Option],
    expected_finish_time: str,
    expected_progress: str,
) -> None:
    """Test the refresh on reconnection replaces the stored program progress."""
    freezer.move_to(PROGRAM_TIMES_TEST_START)
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_RUN)
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {
                    EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1800,
                    EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 10,
                },
            ),
            EventMessage(appliance.ha_id, EventType.DISCONNECTED, ArrayOfEvents([])),
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, STATE_UNAVAILABLE)

    # While disconnected, the program was replaced by another one.
    program_key = ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING
    client.get_all_programs = AsyncMock(
        return_value=ArrayOfPrograms(
            [EnumerateProgram(program_key, program_key.value)],
            active=Program(program_key, options=active_program_options),
        )
    )
    await client.add_events(
        [EventMessage(appliance.ha_id, EventType.CONNECTED, ArrayOfEvents([]))]
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, expected_finish_time)
    assert hass.states.is_state(OVEN_PROGRESS_ENTITY_ID, expected_progress)


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    "end_events",
    [
        pytest.param(
            [(EventType.NOTIFY, {EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: None})],
            id="active_program_cleared",
        ),
        pytest.param(
            [
                (
                    EventType.STATUS,
                    {
                        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
                            BSH_OPERATION_STATE_READY
                        )
                    },
                )
            ],
            id="ready",
        ),
        pytest.param(
            [(EventType.DISCONNECTED, {}), (EventType.CONNECTED, {})],
            id="reconnected_while_ready",
        ),
    ],
)
@pytest.mark.parametrize(
    "start_event_order",
    [
        pytest.param((0, 1, 2), id="progress_program_operation_state"),
        pytest.param((0, 2, 1), id="progress_operation_state_program"),
        pytest.param((1, 0, 2), id="program_progress_operation_state"),
        pytest.param((1, 2, 0), id="program_operation_state_progress"),
        pytest.param((2, 0, 1), id="operation_state_progress_program"),
        pytest.param((2, 1, 0), id="operation_state_program_progress"),
    ],
)
async def test_program_finish_time_on_program_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    end_events: list[tuple[EventType, dict[EventKey, Any]]],
    start_event_order: tuple[int, int, int],
) -> None:
    """Test the progress of a new program is kept regardless of the event order."""
    freezer.move_to(PROGRAM_TIMES_TEST_START)
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_RUN)
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    # Used by the refresh after the reconnection
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_READY)
    )
    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1800},
            ),
            *(
                create_event_message(appliance.ha_id, event_type, items)
                for event_type, items in end_events
            ),
        ]
    )
    await hass.async_block_till_done()

    start_events = (
        create_event_message(
            appliance.ha_id,
            EventType.NOTIFY,
            {
                EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1200,
                EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 0,
            },
        ),
        create_event_message(
            appliance.ha_id,
            EventType.NOTIFY,
            {
                EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                    ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING.value
                )
            },
        ),
        create_event_message(
            appliance.ha_id,
            EventType.STATUS,
            {EventKey.BSH_COMMON_STATUS_OPERATION_STATE: BSH_OPERATION_STATE_RUN},
        ),
    )
    await client.add_events([start_events[index] for index in start_event_order])
    await hass.async_block_till_done()

    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, "2021-01-09T12:20:00+00:00")
    assert hass.states.is_state(OVEN_PROGRESS_ENTITY_ID, "0")


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_program_change_does_not_write_intermediate_states(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test a program change with new progress only writes the new states."""
    freezer.move_to(PROGRAM_TIMES_TEST_START)
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_RUN)
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {
                    EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1800,
                    EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 10,
                },
            )
        ]
    )
    await hass.async_block_till_done()

    written_states: list[tuple[str, str]] = []

    @callback
    def _record_state(event: HassEvent[EventStateChangedData]) -> None:
        if new_state := event.data["new_state"]:
            written_states.append((event.data["entity_id"], new_state.state))

    async_track_state_change_event(
        hass, [OVEN_FINISH_TIME_ENTITY_ID, OVEN_PROGRESS_ENTITY_ID], _record_state
    )
    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {
                    EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                        ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING.value
                    ),
                    EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 600,
                    EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 0,
                },
            )
        ]
    )
    await hass.async_block_till_done()

    assert written_states == [
        (OVEN_FINISH_TIME_ENTITY_ID, "2021-01-09T12:10:00+00:00"),
        (OVEN_PROGRESS_ENTITY_ID, "0"),
    ]


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_program_finish_time_kept_on_pause(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test pausing and resuming a program keeps its progress."""
    freezer.move_to(PROGRAM_TIMES_TEST_START)
    client.get_status = AsyncMock(
        return_value=create_operation_state_status(BSH_OPERATION_STATE_RUN)
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    await client.add_events(
        [
            create_event_message(
                appliance.ha_id,
                EventType.NOTIFY,
                {
                    EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 1800,
                    EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 10,
                },
            ),
            *(
                create_event_message(
                    appliance.ha_id,
                    EventType.STATUS,
                    {EventKey.BSH_COMMON_STATUS_OPERATION_STATE: operation_state},
                )
                for operation_state in (
                    BSH_OPERATION_STATE_PAUSE,
                    BSH_OPERATION_STATE_RUN,
                )
            ),
        ]
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(OVEN_FINISH_TIME_ENTITY_ID, "2021-01-09T12:30:00+00:00")
    assert hass.states.is_state(OVEN_PROGRESS_ENTITY_ID, "10")


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_program_running_time(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test the program running time is rounded to whole minutes."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.is_state(OVEN_RUNNING_TIME_ENTITY_ID, STATE_UNAVAILABLE)

    for events, expected_state in (
        (
            {
                EventType.NOTIFY: {EventKey.BSH_COMMON_OPTION_ELAPSED_PROGRAM_TIME: 0},
                EventType.STATUS: {
                    EventKey.BSH_COMMON_STATUS_OPERATION_STATE: BSH_OPERATION_STATE_RUN
                },
            },
            "0",
        ),
        # The appliance reports the elapsed time shortly before each full minute
        (
            {EventType.NOTIFY: {EventKey.BSH_COMMON_OPTION_ELAPSED_PROGRAM_TIME: 59}},
            "1",
        ),
        (
            {EventType.NOTIFY: {EventKey.BSH_COMMON_OPTION_ELAPSED_PROGRAM_TIME: 119}},
            "2",
        ),
        (
            {
                EventType.NOTIFY: {
                    EventKey.BSH_COMMON_OPTION_ELAPSED_PROGRAM_TIME: 135
                },
                EventType.STATUS: {
                    EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
                        BSH_OPERATION_STATE_PAUSE
                    )
                },
            },
            "2",
        ),
        (
            {
                EventType.STATUS: {
                    EventKey.BSH_COMMON_STATUS_OPERATION_STATE: BSH_OPERATION_STATE_RUN
                }
            },
            "2",
        ),
        (
            {EventType.NOTIFY: {EventKey.BSH_COMMON_OPTION_ELAPSED_PROGRAM_TIME: 179}},
            "3",
        ),
        (
            {
                EventType.STATUS: {
                    EventKey.BSH_COMMON_STATUS_OPERATION_STATE: (
                        BSH_OPERATION_STATE_READY
                    )
                }
            },
            STATE_UNAVAILABLE,
        ),
    ):
        await client.add_events(
            [
                create_event_message(appliance.ha_id, event_type, items)
                for event_type, items in events.items()
            ]
        )
        await hass.async_block_till_done()
        assert hass.states.is_state(OVEN_RUNNING_TIME_ENTITY_ID, expected_state)
