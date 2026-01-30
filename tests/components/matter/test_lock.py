"""Test Matter locks."""

from unittest.mock import AsyncMock, MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntityFeature, LockState
from homeassistant.components.matter.const import (
    ATTR_MAX_CREDENTIALS_PER_USER,
    ATTR_MAX_PIN_USERS,
    ATTR_MAX_RFID_USERS,
    ATTR_MAX_USERS,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    EVENT_LOCK_DISPOSABLE_USER_DELETED,
    EVENT_LOCK_OPERATION,
)
from homeassistant.const import ATTR_CODE, ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

from tests.common import async_capture_events


@pytest.mark.usefixtures("matter_devices")
async def test_locks(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test locks."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.LOCK)


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test door lock."""
    await hass.services.async_call(
        "lock",
        "unlock",
        {
            "entity_id": "lock.mock_door_lock",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.UnlockDoor(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "lock",
        "lock",
        {
            "entity_id": "lock.mock_door_lock",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.LockDoor(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.async_block_till_done()
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.LOCKING

    set_node_attribute(matter_node, 1, 257, 0, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.UNLOCKED

    set_node_attribute(matter_node, 1, 257, 0, 2)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.UNLOCKED

    set_node_attribute(matter_node, 1, 257, 0, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.LOCKED

    set_node_attribute(matter_node, 1, 257, 0, None)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == STATE_UNKNOWN

    # test featuremap update
    set_node_attribute(matter_node, 1, 257, 65532, 4096)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes["supported_features"] & LockEntityFeature.OPEN

    # test handling of a node LockOperation event
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 3},
        ),
    )
    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes[ATTR_CHANGED_BY] == "Keypad"


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_requires_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test door lock with PINCode."""

    code = "1234567"

    # set RequirePINforRemoteOperation
    set_node_attribute(matter_node, 1, 257, 51, True)
    # set door state to unlocked
    set_node_attribute(matter_node, 1, 257, 0, 2)

    await trigger_subscription_callback(hass, matter_client)
    with pytest.raises(ServiceValidationError):
        # Lock door using invalid code format
        await hass.services.async_call(
            "lock",
            "lock",
            {"entity_id": "lock.mock_door_lock", ATTR_CODE: "1234"},
            blocking=True,
        )

    # Lock door using valid code
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": "lock.mock_door_lock", ATTR_CODE: code},
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.LockDoor(code.encode()),
        timed_request_timeout_ms=1000,
    )

    # Lock door using default code
    default_code = "7654321"
    entity_registry.async_update_entity_options(
        "lock.mock_door_lock", "lock", {"default_code": default_code}
    )
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": "lock.mock_door_lock"},
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 2
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.LockDoor(default_code.encode()),
        timed_request_timeout_ms=1000,
    )


@pytest.mark.parametrize("node_fixture", ["door_lock_with_unbolt"])
async def test_lock_with_unbolt(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test door lock."""
    state = hass.states.get("lock.mock_door_lock_with_unbolt")
    assert state
    assert state.state == LockState.LOCKED
    assert state.attributes["supported_features"] & LockEntityFeature.OPEN
    # test unlock/unbolt
    await hass.services.async_call(
        "lock",
        "unlock",
        {
            "entity_id": "lock.mock_door_lock_with_unbolt",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    # unlock should unbolt on a lock with unbolt feature
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.UnboltDoor(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()
    # test open / unlatch
    await hass.services.async_call(
        "lock",
        "open",
        {
            "entity_id": "lock.mock_door_lock_with_unbolt",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.UnlockDoor(),
        timed_request_timeout_ms=1000,
    )

    await hass.async_block_till_done()
    state = hass.states.get("lock.mock_door_lock_with_unbolt")
    assert state
    assert state.state == LockState.OPENING

    set_node_attribute(matter_node, 1, 257, 0, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_with_unbolt")
    assert state
    assert state.state == LockState.UNLOCKED

    set_node_attribute(matter_node, 1, 257, 0, 3)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_with_unbolt")
    assert state
    assert state.state == LockState.OPEN


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_operation_event_with_user_lookup(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock operation event resolves user name from device."""
    events = async_capture_events(hass, EVENT_LOCK_OPERATION)

    # Mock GetUser response for the user lookup triggered by LockOperation event
    matter_client.send_device_command = AsyncMock(
        return_value={
            "userName": "Alice",
            "userType": 0,
            "userStatus": 1,
        }
    )

    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "operationSource": 7,
                "lockOperationType": 1,
                "userIndex": 1,
            },
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_CHANGED_BY] == "Alice (Remote)"

    # Verify the GetUser command was sent
    matter_client.send_device_command.assert_called_once_with(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )

    # Verify the fired event data
    assert len(events) == 1
    event_data = events[0].data
    assert event_data[ATTR_ENTITY_ID] == "lock.mock_door_lock"
    assert event_data["operation"] == "unlock"
    assert event_data["source"] == "Remote"
    assert event_data[ATTR_USER_INDEX] == 1
    assert event_data[ATTR_USER_NAME] == "Alice"


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_operation_event_user_lookup_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock operation event handles user lookup failure gracefully."""
    events = async_capture_events(hass, EVENT_LOCK_OPERATION)

    # Mock GetUser to raise an exception
    matter_client.send_device_command = AsyncMock(
        side_effect=Exception("Device communication error")
    )

    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "operationSource": 3,
                "lockOperationType": 0,
                "userIndex": 5,
            },
        ),
    )

    # Should still update changed_by with source only (no user name)
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_CHANGED_BY] == "Keypad"

    # Event should still fire
    assert len(events) == 1
    assert events[0].data[ATTR_USER_NAME] is None
    assert events[0].data[ATTR_USER_INDEX] == 5


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_operation_event_no_user_index(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock operation event without a user index."""
    events = async_capture_events(hass, EVENT_LOCK_OPERATION)

    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 4, "lockOperationType": 0},
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_CHANGED_BY] == "Auto"

    assert len(events) == 1
    assert events[0].data[ATTR_USER_INDEX] is None
    assert events[0].data[ATTR_USER_NAME] is None


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_disposable_user_cleanup(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test disposable user is cleaned up after one-time use."""
    events = async_capture_events(hass, EVENT_LOCK_DISPOSABLE_USER_DELETED)

    # Mock GetUser returning a disposable user (type=6) in disabled state (status=3)
    # Then mock ClearUser succeeding (returns None)
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {
                "userName": "OneTimeCode",
                "userType": 6,
                "userStatus": 3,
            },
            None,  # ClearUser response
        ]
    )

    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "operationSource": 3,
                "lockOperationType": 1,
                "userIndex": 2,
            },
        ),
    )

    # Verify ClearUser was called for the disposable user
    assert matter_client.send_device_command.call_count == 2
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.ClearUser(userIndex=2),
        timed_request_timeout_ms=1000,
    )

    # Verify the deletion event was fired
    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == "lock.mock_door_lock"
    assert events[0].data[ATTR_USER_INDEX] == 2
    assert events[0].data[ATTR_USER_NAME] == "OneTimeCode"


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_disposable_user_cleanup_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test disposable user cleanup handles failure gracefully."""
    events = async_capture_events(hass, EVENT_LOCK_DISPOSABLE_USER_DELETED)

    # Mock GetUser returning disposable user, then ClearUser failing
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {
                "userName": "FailCode",
                "userType": 6,
                "userStatus": 3,
            },
            Exception("Clear failed"),
        ]
    )

    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={
                "operationSource": 3,
                "lockOperationType": 1,
                "userIndex": 3,
            },
        ),
    )

    # Cleanup failed, so no deletion event should be fired
    assert len(events) == 0

    # changed_by should still be updated from the user lookup
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_CHANGED_BY] == "FailCode (Keypad)"


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_extra_state_attributes_without_usr(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test extra state attributes when USR feature is not supported."""
    # Default door_lock fixture has featuremap=0, no USR support
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_SUPPORTS_USER_MGMT] is False
    assert ATTR_MAX_USERS not in state.attributes
    assert ATTR_MAX_PIN_USERS not in state.attributes
    assert ATTR_MAX_RFID_USERS not in state.attributes
    assert ATTR_MAX_CREDENTIALS_PER_USER not in state.attributes


@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            # Enable USR feature (bit 8 = 256) + PIN (bit 0 = 1)
            "1/257/65532": 257,
        }
    ],
)
async def test_extra_state_attributes_with_usr(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test extra state attributes when USR feature is supported."""
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_SUPPORTS_USER_MGMT] is True
    # Verify capacity attributes are present (from fixture values)
    assert state.attributes[ATTR_MAX_USERS] == 10
    assert state.attributes[ATTR_MAX_PIN_USERS] == 10
    assert state.attributes[ATTR_MAX_RFID_USERS] == 10
    assert state.attributes[ATTR_MAX_CREDENTIALS_PER_USER] == 5


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_extra_state_attributes_dynamic_featuremap(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test extra state attributes update when featuremap changes dynamically."""
    # Initially no USR support
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_SUPPORTS_USER_MGMT] is False

    # Enable USR feature dynamically
    set_node_attribute(matter_node, 1, 257, 65532, 256)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_SUPPORTS_USER_MGMT] is True
    assert ATTR_MAX_USERS in state.attributes
