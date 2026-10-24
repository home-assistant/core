"""Tests for home_connect binary_sensor entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
    StatusKey,
)
from aiohomeconnect.model.error import HomeConnectApiError
from aiohomeconnect.model.program import ProgramKey
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.home_connect.const import (
    BSH_OPERATION_STATE_FINISHED,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_READY,
    BSH_OPERATION_STATE_RUN,
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import create_event_message


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


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
            (StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,),
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
    assert entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{appliance.ha_id}-{EventKey.BSH_COMMON_APPLIANCE_CONNECTED}",
    )
    for key in keys_to_check:
        assert not entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR,
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

    for key in (*keys_to_check, EventKey.BSH_COMMON_APPLIANCE_CONNECTED):
        assert entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR,
            DOMAIN,
            f"{appliance.ha_id}-{key}",
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_binary_sensors_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test binary sensor availability based on appliance connection."""
    entity_ids = [
        "binary_sensor.washer_remote_control",
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


@pytest.mark.parametrize(
    ("entity_id", "event_key", "event_value_update", "expected", "appliance"),
    [
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            False,
            STATE_OFF,
            "Washer",
        ),
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            True,
            STATE_ON,
            "Washer",
        ),
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            "",
            STATE_UNKNOWN,
            "Washer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_CLOSED,
            STATE_OFF,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_OPEN,
            STATE_ON,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            "",
            STATE_UNKNOWN,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance"],
)
async def test_binary_sensors_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    entity_id: str,
    event_key: EventKey,
    event_value_update: str,
    appliance: HomeAppliance,
    expected: str,
) -> None:
    """Tests for Home Connect Fridge appliance door states."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=event_value_update,
                        )
                    ],
                ),
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_connected_sensor_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test if the connected binary sensor reports the right values."""
    entity_id = "binary_sensor.washer_connectivity"
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(entity_id, STATE_ON)

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

    assert hass.states.is_state(entity_id, STATE_OFF)

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

    assert hass.states.is_state(entity_id, STATE_ON)


def _operation_state(operation_state: str) -> tuple[EventType, dict[EventKey, Any]]:
    """Return the event items of an operation state change."""
    return (
        EventType.STATUS,
        {EventKey.BSH_COMMON_STATUS_OPERATION_STATE: operation_state},
    )


def _remaining_program_time(
    seconds: int | None,
) -> tuple[EventType, dict[EventKey, Any]]:
    """Return the event items of a remaining program time update."""
    return (
        EventType.NOTIFY,
        {EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME: seconds},
    )


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_remaining_program_time_set_binary_sensor(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test the binary sensor follows the remaining time of the current program."""
    entity_id = "binary_sensor.oven_remaining_program_time_set"
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    for events, expected_state in (
        ([_operation_state(BSH_OPERATION_STATE_RUN)], STATE_OFF),
        ([_remaining_program_time(1800)], STATE_ON),
        ([_operation_state(BSH_OPERATION_STATE_PAUSE)], STATE_ON),
        ([_operation_state(BSH_OPERATION_STATE_RUN)], STATE_ON),
        ([_remaining_program_time(None)], STATE_OFF),
        ([_remaining_program_time(60)], STATE_ON),
        # The program is aborted and a program without a timer is started
        ([_operation_state(BSH_OPERATION_STATE_READY)], STATE_UNAVAILABLE),
        (
            [
                (
                    EventType.NOTIFY,
                    {
                        EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM: (
                            ProgramKey.COOKING_OVEN_HEATING_MODE_TOP_BOTTOM_HEATING.value
                        )
                    },
                ),
                _operation_state(BSH_OPERATION_STATE_RUN),
            ],
            STATE_OFF,
        ),
        ([_remaining_program_time(0)], STATE_OFF),
        ([_operation_state(BSH_OPERATION_STATE_FINISHED)], STATE_OFF),
    ):
        await client.add_events(
            [
                create_event_message(appliance.ha_id, event_type, items)
                for event_type, items in events
            ]
        )
        await hass.async_block_till_done()
        assert hass.states.is_state(entity_id, expected_state)
