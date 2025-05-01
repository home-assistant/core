"""Tests for home_connect sensor entities."""

from collections.abc import Awaitable, Callable
import logging
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
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.home_connect.const import (
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    BSH_EVENT_PRESENT_STATE_CONFIRMED,
    BSH_EVENT_PRESENT_STATE_OFF,
    BSH_EVENT_PRESENT_STATE_PRESENT,
    DOMAIN,
)
from homeassistant.components.home_connect.coordinator import HomeConnectError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_HC_APP = "Dishwasher"


EVENT_PROG_DELAYED_START = {
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: "BSH.Common.EnumType.OperationState.DelayedStart",
    },
}


EVENT_PROG_RUN = {
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: "BSH.Common.EnumType.OperationState.Run",
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
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: "BSH.Common.EnumType.OperationState.Run",
    },
}

EVENT_PROG_UPDATE_2 = {
    EventType.EVENT: {
        EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: 20,
        EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS: 99,
    },
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: "BSH.Common.EnumType.OperationState.Run",
    },
}

EVENT_PROG_END = {
    EventType.STATUS: {
        EventKey.BSH_COMMON_STATUS_OPERATION_STATE: "BSH.Common.EnumType.OperationState.Ready",
    },
}


@pytest.fixture
def platforms() -> list[str]:
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
    """Test that removed devices are correctly removed from and added to hass on API events."""
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
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

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
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

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.EVENT,
                ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.LAUNDRY_CARE_WASHER_EVENT_I_DOS_1_FILL_LEVEL_POOR,
                            raw_key=EventKey.LAUNDRY_CARE_WASHER_EVENT_I_DOS_1_FILL_LEVEL_POOR.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=BSH_EVENT_PRESENT_STATE_PRESENT,
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state("sensor.washer_poor_i_dos_1_fill_level", "present")


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
    assert config_entry.state == ConfigEntryState.LOADED
    client.get_status = get_status_original_mock

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
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


@pytest.mark.parametrize("appliance", [TEST_HC_APP], indirect=True)
async def test_sensor_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if sensor entities availability are based on the appliance connection state."""
    entity_ids = [
        "sensor.dishwasher_operation_state",
        "sensor.dishwasher_salt_nearly_empty",
    ]
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.EVENT,
                ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
                            raw_key=EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=BSH_EVENT_PRESENT_STATE_OFF,
                        )
                    ],
                ),
            ),
        ]
    )
    await hass.async_block_till_done()

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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    client.get_status.return_value.status.extend(
        Status(
            key=StatusKey(event_key.value),
            raw_key=event_key.value,
            value=value,
        )
        for event_key, value in EVENT_PROG_DELAYED_START[EventType.STATUS].items()
    )
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

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
    assert config_entry.state == ConfigEntryState.LOADED

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
    "unavailable",
    "2021-01-09T12:00:01+00:00",
    "unavailable",
    "unavailable",
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
    assert config_entry.state == ConfigEntryState.LOADED

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


@pytest.mark.parametrize(
    (
        "entity_id",
        "event_key",
        "value_expected_state",
        "appliance",
    ),
    [
        (
            "sensor.dishwasher_door",
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            [
                (
                    BSH_DOOR_STATE_LOCKED,
                    "locked",
                ),
                (
                    BSH_DOOR_STATE_CLOSED,
                    "closed",
                ),
                (
                    BSH_DOOR_STATE_OPEN,
                    "open",
                ),
            ],
            "Dishwasher",
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
    value_expected_state: list[tuple[str, str]],
    appliance: HomeAppliance,
) -> None:
    """Tests for appliance sensors."""
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for value, expected_state in value_expected_state:
        await client.add_events(
            [
                EventMessage(
                    appliance.ha_id,
                    EventType.STATUS,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=str(event_key),
                                timestamp=0,
                                level="",
                                handling="",
                                value=value,
                            )
                        ],
                    ),
                ),
            ]
        )
        await hass.async_block_till_done()
        assert hass.states.is_state(entity_id, expected_state)


@pytest.mark.parametrize(
    (
        "entity_id",
        "event_key",
        "appliance",
    ),
    [
        (
            "sensor.fridgefreezer_freezer_door_alarm",
            EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
            "FridgeFreezer",
        ),
        (
            "sensor.coffeemaker_bean_container_empty",
            EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
            "CoffeeMaker",
        ),
    ],
    indirect=["appliance"],
)
async def test_event_sensors_states(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_id: str,
    event_key: EventKey,
    appliance: HomeAppliance,
) -> None:
    """Tests for appliance event sensors."""
    caplog.set_level(logging.ERROR)
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert not hass.states.get(entity_id)

    for value, expected_state in (
        (BSH_EVENT_PRESENT_STATE_OFF, "off"),
        (BSH_EVENT_PRESENT_STATE_PRESENT, "present"),
        (BSH_EVENT_PRESENT_STATE_CONFIRMED, "confirmed"),
    ):
        await client.add_events(
            [
                EventMessage(
                    appliance.ha_id,
                    EventType.EVENT,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=str(event_key),
                                timestamp=0,
                                level="",
                                handling="",
                                value=value,
                            )
                        ],
                    ),
                ),
            ]
        )
        await hass.async_block_till_done()
        assert hass.states.is_state(entity_id, expected_state)

    # Verify that the integration doesn't attempt to add the event sensors more than once
    # If that happens, the EntityPlatform logs an error with the entity's unique ID.
    assert "exists" not in caplog.text
    assert entity_id not in caplog.text
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.unique_id not in caplog.text


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
    assert config_entry.state == ConfigEntryState.LOADED

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
    assert config_entry.state == ConfigEntryState.LOADED

    assert hass.states.get(entity_id)


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
            TooManyRequestsError("error.key", retry_after=0),
            Status(
                key=status_key,
                raw_key=status_key.value,
                value=0,
                unit=unit,
            ),
        ]
    )

    assert await integration_setup(client)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert client.get_status_value.call_count == 2

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes["unit_of_measurement"] == unit
