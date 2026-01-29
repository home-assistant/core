"""Test Matter Event entities."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import snapshot_matter_entities, trigger_subscription_callback


@pytest.mark.usefixtures("matter_devices")
async def test_events(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test events."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.EVENT)


@pytest.mark.parametrize("node_fixture", ["generic_switch"])
async def test_generic_switch_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node."""
    state = hass.states.get("event.mock_generic_switch_button")
    assert state
    assert state.state == "unknown"
    assert state.name == "Mock Generic Switch Button"
    # check event_types from featuremap 14 (0b1110)
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "initial_press",
        "short_release",
        "long_press",
        "long_release",
    ]
    # trigger firing a new event from the device
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=1,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )
    state = hass.states.get("event.mock_generic_switch_button")
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"


@pytest.mark.parametrize("node_fixture", ["generic_switch_multi"])
async def test_generic_switch_multi_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a GenericSwitch node with multiple buttons."""
    state_button_1 = hass.states.get("event.mock_generic_switch_button_1")
    assert state_button_1
    assert state_button_1.state == "unknown"
    # name should be 'DeviceName Button (1)' due to the label set to just '1'
    assert state_button_1.name == "Mock Generic Switch Button (1)"
    # check event_types from featuremap 30 (0b11110) and MultiPressMax unset (default 2)
    assert state_button_1.attributes[ATTR_EVENT_TYPES] == [
        "multi_press_1",
        "multi_press_2",
        "long_press",
        "long_release",
    ]
    # check button 2
    state_button_2 = hass.states.get("event.mock_generic_switch_button_2")
    assert state_button_2
    assert state_button_2.state == "unknown"
    # name should be 'DeviceName Button (2)'
    assert state_button_2.name == "Mock Generic Switch Button (2)"
    # check event_types from featuremap 30 (0b11110) and MultiPressMax 4
    assert state_button_2.attributes[ATTR_EVENT_TYPES] == [
        "multi_press_1",
        "multi_press_2",
        "multi_press_3",
        "multi_press_4",
        "long_press",
        "long_release",
    ]

    # trigger firing a multi press event
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=6,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"totalNumberOfPressesCounted": 2},
        ),
    )
    state = hass.states.get("event.mock_generic_switch_button_1")
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_2"


# DoorLock cluster ID is 257
DOOR_LOCK_CLUSTER_ID = 257


@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_lock_alarm_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock alarm event entity."""
    state = hass.states.get("event.mock_door_lock_with_usr_lock_alarm")
    assert state
    assert state.state == "unknown"
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "lock_jammed",
        "lock_factory_reset",
        "lock_radio_power_cycled",
        "wrong_code_entry_limit",
        "front_escutcheon_removed",
        "door_forced_open",
        "door_ajar",
        "forced_user",
    ]

    # Trigger a lock jammed alarm event (alarmCode=0)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=0,  # DoorLockAlarm
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"alarmCode": 0},
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_lock_alarm")
    assert state.attributes[ATTR_EVENT_TYPE] == "lock_jammed"

    # Trigger a wrong code entry limit alarm event (alarmCode=3)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=0,  # DoorLockAlarm
            event_number=1,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"alarmCode": 3},
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_lock_alarm")
    assert state.attributes[ATTR_EVENT_TYPE] == "wrong_code_entry_limit"


@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_lock_operation_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock operation event entity."""
    state = hass.states.get("event.mock_door_lock_with_usr_lock_operation")
    assert state
    assert state.state == "unknown"
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "locked",
        "unlocked",
        "unlatched",
        "lock_failed",
        "unlock_failed",
        "unlatch_failed",
    ]

    # Trigger a lock operation event (lockOperationType=0 for lock)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=2,  # LockOperation
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"lockOperationType": 0, "operationSource": 3, "userIndex": 1},
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_lock_operation")
    assert state.attributes[ATTR_EVENT_TYPE] == "locked"
    # Check enriched data
    assert state.attributes.get("operation_type") == "lock"
    assert state.attributes.get("source") == "keypad"
    assert state.attributes.get("user_index") == 1

    # Trigger an unlock operation event (lockOperationType=1 for unlock)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=2,  # LockOperation
            event_number=1,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"lockOperationType": 1, "operationSource": 7, "userIndex": 2},
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_lock_operation")
    assert state.attributes[ATTR_EVENT_TYPE] == "unlocked"
    assert state.attributes.get("source") == "remote"


@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_lock_operation_error_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock operation error event entity."""
    state = hass.states.get("event.mock_door_lock_with_usr_lock_operation")
    assert state

    # Trigger a lock operation error event (lockOperationType=1 for unlock, failed)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=3,  # LockOperationError
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "lockOperationType": 1,
                "operationSource": 3,
                "operationError": 1,
                "userIndex": None,
            },
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_lock_operation")
    assert state.attributes[ATTR_EVENT_TYPE] == "unlock_failed"
    assert state.attributes.get("error") == "invalid_credential"
    assert state.attributes.get("source") == "keypad"


@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_lock_user_change_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock user change event entity."""
    state = hass.states.get("event.mock_door_lock_with_usr_user_change")
    assert state
    assert state.state == "unknown"
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "user_added",
        "user_cleared",
        "user_modified",
        "credential_added",
        "credential_cleared",
        "credential_modified",
    ]

    # Trigger a user added event (lockDataType=2 for UserIndex, dataOperationType=0 for Add)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=4,  # LockUserChange
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "lockDataType": 2,
                "dataOperationType": 0,
                "operationSource": 7,
                "userIndex": 1,
                "dataIndex": None,
            },
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_user_change")
    assert state.attributes[ATTR_EVENT_TYPE] == "user_added"
    assert state.attributes.get("data_type") == "user_index"
    assert state.attributes.get("operation") == "add"
    assert state.attributes.get("source") == "remote"
    assert state.attributes.get("user_index") == 1

    # Trigger a credential added event (lockDataType=6 for PIN, dataOperationType=0 for Add)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=DOOR_LOCK_CLUSTER_ID,
            event_id=4,  # LockUserChange
            event_number=1,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "lockDataType": 6,
                "dataOperationType": 0,
                "operationSource": 7,
                "userIndex": 1,
                "dataIndex": 1,
            },
        ),
    )
    state = hass.states.get("event.mock_door_lock_with_usr_user_change")
    assert state.attributes[ATTR_EVENT_TYPE] == "credential_added"
    assert state.attributes.get("data_type") == "pin"
    assert state.attributes.get("data_index") == 1
