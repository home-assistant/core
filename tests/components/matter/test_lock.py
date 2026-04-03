"""Test Matter locks."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from chip.clusters import Objects as clusters
from chip.clusters.Objects import NullValue
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntityFeature, LockState
from homeassistant.components.matter.const import (
    ATTR_CREDENTIAL_DATA,
    ATTR_CREDENTIAL_INDEX,
    ATTR_CREDENTIAL_RULE,
    ATTR_CREDENTIAL_TYPE,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    CLEAR_ALL_INDEX,
    DOMAIN,
)
from homeassistant.const import ATTR_CODE, ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

# Feature map bits
_FEATURE_PIN = 1  # kPinCredential (bit 0)
_FEATURE_RFID = 2  # kRfidCredential (bit 1)
_FEATURE_FINGER = 4  # kFingerCredentials (bit 2)
_FEATURE_USR = 256  # kUser (bit 8)
_FEATURE_USR_PIN = _FEATURE_USR | _FEATURE_PIN  # 257
_FEATURE_USR_RFID = _FEATURE_USR | _FEATURE_RFID  # 258
_FEATURE_USR_PIN_RFID = _FEATURE_USR | _FEATURE_PIN | _FEATURE_RFID  # 259
_FEATURE_USR_FINGER = _FEATURE_USR | _FEATURE_FINGER  # 260


@pytest.mark.usefixtures("matter_devices")
async def test_locks(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test locks."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.LOCK)


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
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
        timed_request_timeout_ms=10000,
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
        timed_request_timeout_ms=10000,
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
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
        timed_request_timeout_ms=10000,
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
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock_with_unbolt"])
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
        timed_request_timeout_ms=10000,
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
        timed_request_timeout_ms=10000,
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_lock_operation_updates_changed_by(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock operation event updates changed_by with source."""
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
            data={"operationSource": 7, "lockOperationType": 1},
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.attributes[ATTR_CHANGED_BY] == "Remote"


# --- Entity service tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_service(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user entity service creates user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser(1): empty slot
            None,  # SetUser: success
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "set_lock_user",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_NAME: "TestUser",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    # Verify GetUser was called to find empty slot
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )
    # Verify SetUser was called with kAdd operation
    set_user_cmd = matter_client.send_device_command.call_args_list[1]
    assert set_user_cmd == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            userIndex=1,
            userName="TestUser",
            userUniqueID=None,
            userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
            userType=clusters.DoorLock.Enums.UserTypeEnum.kUnrestrictedUser,
            credentialRule=clusters.DoorLock.Enums.CredentialRuleEnum.kSingle,
        ),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_update_existing(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user service updates existing user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # GetUser: existing user
                "userStatus": 1,
                "userName": "Old Name",
                "userUniqueID": 123,
                "userType": 0,
                "credentialRule": 0,
                "credentials": None,
            },
            None,  # SetUser: modify
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "set_lock_user",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "New Name",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    # Verify GetUser was called to check existing user
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )
    # Verify SetUser was called with kModify, preserving existing values
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
            userIndex=1,
            userName="New Name",
            userUniqueID=123,
            userStatus=1,  # Preserved from existing user
            userType=0,  # Preserved from existing user
            credentialRule=0,  # Preserved from existing user
        ),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_no_available_slots(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user when no user slots are available."""
    # All user slots are occupied
    matter_client.send_device_command = AsyncMock(
        return_value={"userStatus": 1}  # All slots occupied
    )

    with pytest.raises(ServiceValidationError, match="No available user slots"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_user",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "Test User",
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_empty_slot_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user errors when updating non-existent user."""
    matter_client.send_device_command = AsyncMock(
        return_value={"userStatus": None}  # User doesn't exist
    )

    with pytest.raises(ServiceValidationError, match="is empty"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_user",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_INDEX: 5,
                ATTR_USER_NAME: "Test User",
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_user_service(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_user entity service."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    await hass.services.async_call(
        DOMAIN,
        "clear_lock_user",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
        },
        blocking=True,
    )

    # ClearUser handles credential cleanup per the Matter spec
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.ClearUser(userIndex=1),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_info_service(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_info entity service returns capabilities."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_info",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "supports_user_management": True,
        "supported_credential_types": ["pin"],
        "max_users": 10,
        "max_pin_users": 10,
        "max_rfid_users": 10,
        "max_credentials_per_user": 5,
        "min_pin_length": 6,
        "max_pin_length": 8,
        "min_rfid_length": 10,
        "max_rfid_length": 20,
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_users_service(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_users entity service returns users."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {
                "userIndex": 1,
                "userName": "Alice",
                "userUniqueID": None,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
                "credentials": None,
                "nextUserIndex": None,
            },
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_users",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    # Verify GetUser command was sent
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )

    assert result["lock.mock_door_lock"] == {
        "max_users": 10,
        "users": [
            {
                "user_index": 1,
                "user_name": "Alice",
                "user_unique_id": None,
                "user_status": "occupied_enabled",
                "user_type": "unrestricted_user",
                "credential_rule": "single",
                "credentials": [],
                "next_user_index": None,
            }
        ],
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_service_on_lock_without_user_management(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test entity services on lock without USR feature raise error."""
    # Default door_lock fixture has featuremap=0, no USR support
    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_user",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "Test",
            },
            blocking=True,
        )

    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            "clear_lock_user",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_INDEX: 1,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_on_matter_node_event_filters_non_matching_events(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that node events for different endpoints/clusters are filtered."""
    state = hass.states.get("lock.mock_door_lock")
    assert state is not None
    original_changed_by = state.attributes.get(ATTR_CHANGED_BY)

    # Fire event for different endpoint - should be ignored
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=99,  # Different endpoint
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 7},  # Remote source
        ),
    )

    # changed_by should not have changed
    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes.get(ATTR_CHANGED_BY) == original_changed_by

    # Fire event for different cluster - should also be ignored
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=999,  # Different cluster
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 7},
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes.get(ATTR_CHANGED_BY) == original_changed_by


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_users_iterates_with_next_index(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_users uses nextUserIndex for efficient iteration."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # First user at index 1
                "userIndex": 1,
                "userStatus": 1,
                "userName": "User 1",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
                "credentials": None,
                "nextUserIndex": 5,  # Next user at index 5
            },
            {  # Second user at index 5
                "userIndex": 5,
                "userStatus": 1,
                "userName": "User 5",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
                "credentials": None,
                "nextUserIndex": None,  # No more users
            },
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_users",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert matter_client.send_device_command.call_count == 2
    # Verify it jumped from index 1 to index 5 via nextUserIndex
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=5),
    )

    entity_result = result["lock.mock_door_lock"]
    assert entity_result == {
        "max_users": 10,
        "users": [
            {
                "user_index": 1,
                "user_name": "User 1",
                "user_unique_id": None,
                "user_status": "occupied_enabled",
                "user_type": "unrestricted_user",
                "credential_rule": "single",
                "credentials": [],
                "next_user_index": 5,
            },
            {
                "user_index": 5,
                "user_name": "User 5",
                "user_unique_id": None,
                "user_status": "occupied_enabled",
                "user_type": "unrestricted_user",
                "credential_rule": "single",
                "credentials": [],
                "next_user_index": None,
            },
        ],
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/51": True,  # RequirePINforRemoteOperation (attribute 51)
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_code_format_property_with_pin_required(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test code_format property returns regex when PIN is required."""
    state = hass.states.get("lock.mock_door_lock")
    assert state is not None
    # code_format should be set when RequirePINforRemoteOperation is True
    # The format should be a regex like ^\d{4,8}$
    code_format = state.attributes.get("code_format")
    assert code_format is not None
    assert "\\d" in code_format


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_users_next_user_index_loop_prevention(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_users handles nextUserIndex <= current to prevent loops."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # User at index 1
                "userIndex": 1,
                "userStatus": 1,
                "userName": "User 1",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
                "credentials": None,
                "nextUserIndex": 1,  # Same as current - should break loop
            },
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_users",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )

    assert result is not None
    # Result is keyed by entity_id
    lock_users = result["lock.mock_door_lock"]
    assert len(lock_users["users"]) == 1
    # Should have stopped after first user due to nextUserIndex <= current


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_users_with_credentials(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_users returns credential info for users."""
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # User with credentials
                "userIndex": 1,
                "userStatus": 1,
                "userName": "User With PIN",
                "userUniqueID": 123,
                "userType": 0,
                "credentialRule": 0,
                "credentials": [
                    {"credentialType": pin_cred_type, "credentialIndex": 1},
                    {"credentialType": pin_cred_type, "credentialIndex": 2},
                ],
                "nextUserIndex": None,
            },
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_users",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )

    assert result["lock.mock_door_lock"] == {
        "max_users": 10,
        "users": [
            {
                "user_index": 1,
                "user_name": "User With PIN",
                "user_unique_id": 123,
                "user_status": "occupied_enabled",
                "user_type": "unrestricted_user",
                "credential_rule": "single",
                "credentials": [
                    {"type": "pin", "index": 1},
                    {"type": "pin", "index": 2},
                ],
                "next_user_index": None,
            }
        ],
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_users_with_nullvalue_credentials(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_users handles NullValue credentials from Matter SDK."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {
                "userIndex": 1,
                "userStatus": 1,
                "userName": "User No Creds",
                "userUniqueID": 100,
                "userType": 0,
                "credentialRule": 0,
                "credentials": NullValue,
                "nextUserIndex": None,
            },
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_users",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetUser(userIndex=1),
    )

    lock_users = result["lock.mock_door_lock"]
    assert len(lock_users["users"]) == 1
    user = lock_users["users"][0]
    assert user["user_index"] == 1
    assert user["user_name"] == "User No Creds"
    assert user["user_unique_id"] == 100
    assert user["credentials"] == []


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
@pytest.mark.parametrize(
    ("service_name", "service_data", "return_response"),
    [
        ("set_lock_user", {ATTR_USER_NAME: "Test"}, False),
        ("clear_lock_user", {ATTR_USER_INDEX: 1}, False),
        ("get_lock_users", {}, True),
        (
            "set_lock_credential",
            {
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "123456",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            True,
        ),
        (
            "clear_lock_credential",
            {ATTR_CREDENTIAL_TYPE: "pin", ATTR_CREDENTIAL_INDEX: 1},
            False,
        ),
        (
            "get_lock_credential_status",
            {ATTR_CREDENTIAL_TYPE: "pin", ATTR_CREDENTIAL_INDEX: 1},
            True,
        ),
    ],
)
async def test_matter_error_converted_to_home_assistant_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    service_name: str,
    service_data: dict[str, Any],
    return_response: bool,
) -> None:
    """Test that MatterError from helpers is converted to HomeAssistantError."""
    # Simulate a MatterError from the device command
    matter_client.send_device_command = AsyncMock(
        side_effect=MatterError("Device communication failed")
    )

    with pytest.raises(HomeAssistantError, match="Device communication failed"):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {ATTR_ENTITY_ID: "lock.mock_door_lock", **service_data},
            blocking=True,
            return_response=return_response,
        )

    # Verify a command was attempted before the error
    assert matter_client.send_device_command.call_count >= 1


# --- Credential service tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential with PIN type."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus: slot occupied -> kModify
            {"credentialExists": True, "userIndex": 1, "nextCredentialIndex": 2},
            # SetCredential response
            {"status": 0, "userIndex": 1, "nextCredentialIndex": 2},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "1234",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "credential_index": 1,
        "user_index": 1,
        "next_credential_index": 2,
    }

    assert matter_client.send_device_command.call_count == 2
    # Verify GetCredentialStatus was called first
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetCredentialStatus(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                credentialIndex=1,
            ),
        ),
    )
    # Verify SetCredential was called with kModify (occupied slot)
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                credentialIndex=1,
            ),
            credentialData=b"1234",
            userIndex=None,
            userStatus=None,
            userType=None,
        ),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/18": 3,  # NumberOfPINUsersSupported
            "1/257/28": 2,  # NumberOfCredentialsSupportedPerUser (must NOT be used)
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_auto_find_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential auto-finds first available PIN slot."""
    # Place the empty slot at index 3 (the last position within
    # NumberOfPINUsersSupported=3) so the test would fail if the code
    # used NumberOfCredentialsSupportedPerUser=2 instead.
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus(1): occupied
            {"credentialExists": True, "userIndex": 1, "nextCredentialIndex": 2},
            # GetCredentialStatus(2): occupied
            {"credentialExists": True, "userIndex": 2, "nextCredentialIndex": 3},
            # GetCredentialStatus(3): empty — found at the bound limit
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": None,
            },
            # SetCredential response
            {"status": 0, "userIndex": 1, "nextCredentialIndex": None},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "5678",
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "credential_index": 3,
        "user_index": 1,
        "next_credential_index": None,
    }

    # 3 GetCredentialStatus calls + 1 SetCredential = 4 total
    assert matter_client.send_device_command.call_count == 4
    # Verify SetCredential was called with kAdd for the empty slot at index 3
    set_cred_cmd = matter_client.send_device_command.call_args_list[3]
    assert (
        set_cred_cmd.kwargs["command"].operationType
        == clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd
    )
    assert set_cred_cmd.kwargs["command"].credential.credentialIndex == 3


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_with_user_index(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential passes user_index to command."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus: empty slot
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": 2,
            },
            # SetCredential response
            {"status": 0, "userIndex": 3, "nextCredentialIndex": 2},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "1234",
            ATTR_CREDENTIAL_INDEX: 1,
            ATTR_USER_INDEX: 3,
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "credential_index": 1,
        "user_index": 3,
        "next_credential_index": 2,
    }

    # Verify user_index was passed in SetCredential command
    set_cred_call = matter_client.send_device_command.call_args_list[1]
    assert set_cred_call.kwargs["command"].userIndex == 3


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_invalid_pin_too_short(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects PIN that is too short."""
    with pytest.raises(ServiceValidationError, match="PIN length must be between"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "12",  # Too short (min 4)
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_invalid_pin_non_digit(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects non-digit PIN."""
    with pytest.raises(ServiceValidationError, match="PIN must contain only digits"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "abcd",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR}])
async def test_set_lock_credential_unsupported_type(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects unsupported credential type."""
    # USR feature set but no PIN credential feature
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_status_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential raises error on non-success status."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus: empty
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": 2,
            },
            # SetCredential response with duplicate status
            {"status": 2, "userIndex": None, "nextCredentialIndex": None},
        ]
    )

    with pytest.raises(HomeAssistantError, match="duplicate"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/18": 3,  # NumberOfPINUsersSupported
            "1/257/28": 5,  # NumberOfCredentialsSupportedPerUser (should NOT be used)
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_no_available_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential raises error when all slots are full."""
    # All GetCredentialStatus calls return occupied
    matter_client.send_device_command = AsyncMock(
        return_value={
            "credentialExists": True,
            "userIndex": 1,
            "nextCredentialIndex": None,
        }
    )

    with pytest.raises(ServiceValidationError, match="No available credential slots"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
            },
            blocking=True,
            return_response=True,
        )

    # Verify it iterated over NumberOfPINUsersSupported (3), not
    # NumberOfCredentialsSupportedPerUser (5)
    assert matter_client.send_device_command.call_count == 3
    pin_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    for idx in range(3):
        assert matter_client.send_device_command.call_args_list[idx] == call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=pin_type,
                    credentialIndex=idx + 1,
                ),
            ),
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/18": None,  # NumberOfPINUsersSupported not available
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_auto_find_defaults_to_five(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential falls back to 5 slots when capacity attribute is None."""
    # All GetCredentialStatus calls return occupied
    matter_client.send_device_command = AsyncMock(
        return_value={
            "credentialExists": True,
            "userIndex": 1,
            "nextCredentialIndex": None,
        }
    )

    with pytest.raises(ServiceValidationError, match="No available credential slots"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
            },
            blocking=True,
            return_response=True,
        )

    # With NumberOfPINUsersSupported=None, falls back to default of 5
    assert matter_client.send_device_command.call_count == 5
    pin_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    for idx in range(5):
        assert matter_client.send_device_command.call_args_list[idx] == call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=pin_type,
                    credentialIndex=idx + 1,
                ),
            ),
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_credential(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_credential sends ClearCredential command."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    await hass.services.async_call(
        DOMAIN,
        "clear_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.ClearCredential(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                credentialIndex=1,
            ),
        ),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_credential_status(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_credential_status returns credential info."""
    matter_client.send_device_command = AsyncMock(
        return_value={
            "credentialExists": True,
            "userIndex": 2,
            "nextCredentialIndex": 3,
        }
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_credential_status",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetCredentialStatus(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                credentialIndex=1,
            ),
        ),
    )
    assert result["lock.mock_door_lock"] == {
        "credential_exists": True,
        "user_index": 2,
        "next_credential_index": 3,
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_credential_status_empty_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_credential_status for empty slot."""
    matter_client.send_device_command = AsyncMock(
        return_value={
            "credentialExists": False,
            "userIndex": None,
            "nextCredentialIndex": None,
        }
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_credential_status",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_INDEX: 5,
        },
        blocking=True,
        return_response=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.GetCredentialStatus(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kPin,
                credentialIndex=5,
            ),
        ),
    )

    assert result["lock.mock_door_lock"] == {
        "credential_exists": False,
        "user_index": None,
        "next_credential_index": None,
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_credential_services_without_usr_feature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test credential services raise error without USR feature."""
    # Default door_lock fixture has featuremap=0, no USR support
    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )

    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            "clear_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
        )

    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            "get_lock_credential_status",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


# --- RFID credential tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_RFID,
            "1/257/26": 4,  # MinRFIDCodeLength
            "1/257/25": 20,  # MaxRFIDCodeLength
        }
    ],
)
async def test_set_lock_credential_rfid(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential with RFID type using hex data."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus: empty slot
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": 2,
            },
            # SetCredential response
            {"status": 0, "userIndex": 1, "nextCredentialIndex": 2},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "rfid",
            ATTR_CREDENTIAL_DATA: "AABBCCDD",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "credential_index": 1,
        "user_index": 1,
        "next_credential_index": 2,
    }

    assert matter_client.send_device_command.call_count == 2
    # Verify SetCredential was called with RFID type and hex-decoded bytes
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetCredential(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kRfid,
                credentialIndex=1,
            ),
            credentialData=bytes.fromhex("AABBCCDD"),
            userIndex=None,
            userStatus=None,
            userType=None,
        ),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_RFID,
            "1/257/19": 3,  # NumberOfRFIDUsersSupported
            "1/257/28": 2,  # NumberOfCredentialsSupportedPerUser (must NOT be used)
            "1/257/26": 4,  # MinRFIDCodeLength
            "1/257/25": 20,  # MaxRFIDCodeLength
        }
    ],
)
async def test_set_lock_credential_rfid_auto_find_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential auto-finds RFID slot using NumberOfRFIDUsersSupported."""
    # Place the empty slot at index 3 (the last position within
    # NumberOfRFIDUsersSupported=3) so the test would fail if the code
    # used a smaller bound like NumberOfCredentialsSupportedPerUser=2
    # or stopped iterating too early.
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus(1): occupied
            {"credentialExists": True, "userIndex": 1, "nextCredentialIndex": 2},
            # GetCredentialStatus(2): occupied
            {"credentialExists": True, "userIndex": 2, "nextCredentialIndex": 3},
            # GetCredentialStatus(3): empty — found at the bound limit
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": None,
            },
            # SetCredential response
            {"status": 0, "userIndex": 1, "nextCredentialIndex": None},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "rfid",
            ATTR_CREDENTIAL_DATA: "AABBCCDD",
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "credential_index": 3,
        "user_index": 1,
        "next_credential_index": None,
    }

    # 3 GetCredentialStatus calls + 1 SetCredential = 4 total
    assert matter_client.send_device_command.call_count == 4
    # Verify SetCredential was called with kAdd for the empty slot at index 3
    set_cred_cmd = matter_client.send_device_command.call_args_list[3]
    assert (
        set_cred_cmd.kwargs["command"].operationType
        == clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd
    )
    assert set_cred_cmd.kwargs["command"].credential.credentialIndex == 3
    assert (
        set_cred_cmd.kwargs["command"].credential.credentialType
        == clusters.DoorLock.Enums.CredentialTypeEnum.kRfid
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_RFID,
            "1/257/19": 3,  # NumberOfRFIDUsersSupported
            "1/257/28": 5,  # NumberOfCredentialsSupportedPerUser (should NOT be used)
            "1/257/26": 4,  # MinRFIDCodeLength
            "1/257/25": 20,  # MaxRFIDCodeLength
        }
    ],
)
async def test_set_lock_credential_rfid_no_available_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential RFID raises error when all slots are full."""
    matter_client.send_device_command = AsyncMock(
        return_value={
            "credentialExists": True,
            "userIndex": 1,
            "nextCredentialIndex": None,
        }
    )

    with pytest.raises(ServiceValidationError, match="No available credential slots"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "rfid",
                ATTR_CREDENTIAL_DATA: "AABBCCDD",
            },
            blocking=True,
            return_response=True,
        )

    # Verify it iterated over NumberOfRFIDUsersSupported (3), not
    # NumberOfCredentialsSupportedPerUser (5)
    assert matter_client.send_device_command.call_count == 3
    rfid_type = clusters.DoorLock.Enums.CredentialTypeEnum.kRfid
    for idx in range(3):
        assert matter_client.send_device_command.call_args_list[idx] == call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.DoorLock.Commands.GetCredentialStatus(
                credential=clusters.DoorLock.Structs.CredentialStruct(
                    credentialType=rfid_type,
                    credentialIndex=idx + 1,
                ),
            ),
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_FINGER,
            "1/257/17": 3,  # NumberOfTotalUsersSupported (fallback for biometrics)
            "1/257/18": 10,  # NumberOfPINUsersSupported (should NOT be used)
            "1/257/28": 2,  # NumberOfCredentialsSupportedPerUser (should NOT be used)
        }
    ],
)
async def test_set_lock_credential_fingerprint_auto_find_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential auto-finds fingerprint slot using NumberOfTotalUsersSupported."""
    # Place the empty slot at index 3 (the last position within
    # NumberOfTotalUsersSupported=3) so the test would fail if the code
    # used NumberOfPINUsersSupported (10) or NumberOfCredentialsSupportedPerUser (2).
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus(1): occupied
            {"credentialExists": True, "userIndex": 1, "nextCredentialIndex": 2},
            # GetCredentialStatus(2): occupied
            {"credentialExists": True, "userIndex": 2, "nextCredentialIndex": 3},
            # GetCredentialStatus(3): empty — found at the bound limit
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": None,
            },
            # SetCredential response
            {"status": 0, "userIndex": 1, "nextCredentialIndex": None},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "fingerprint",
            ATTR_CREDENTIAL_DATA: "AABBCCDD",
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "credential_index": 3,
        "user_index": 1,
        "next_credential_index": None,
    }

    # 3 GetCredentialStatus calls + 1 SetCredential = 4 total
    assert matter_client.send_device_command.call_count == 4
    # Verify SetCredential was called with kAdd for the empty slot at index 3
    set_cred_cmd = matter_client.send_device_command.call_args_list[3]
    assert (
        set_cred_cmd.kwargs["command"].operationType
        == clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd
    )
    assert set_cred_cmd.kwargs["command"].credential.credentialIndex == 3
    assert (
        set_cred_cmd.kwargs["command"].credential.credentialType
        == clusters.DoorLock.Enums.CredentialTypeEnum.kFingerprint
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_RFID,
            "1/257/26": 4,  # MinRFIDCodeLength
            "1/257/25": 20,  # MaxRFIDCodeLength
        }
    ],
)
async def test_set_lock_credential_rfid_invalid_hex(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects invalid hex RFID data."""
    with pytest.raises(
        ServiceValidationError, match="RFID data must be valid hexadecimal"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "rfid",
                ATTR_CREDENTIAL_DATA: "ZZZZ",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_RFID,
            "1/257/26": 4,  # MinRFIDCodeLength (bytes)
            "1/257/25": 20,  # MaxRFIDCodeLength (bytes)
        }
    ],
)
async def test_set_lock_credential_rfid_too_short(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects RFID data below min byte length."""
    # "AABB" = 2 bytes, min is 4
    with pytest.raises(
        ServiceValidationError, match="RFID data length must be between"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "rfid",
                ATTR_CREDENTIAL_DATA: "AABB",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_RFID,
            "1/257/26": 4,  # MinRFIDCodeLength (bytes)
            "1/257/25": 6,  # MaxRFIDCodeLength (bytes)
        }
    ],
)
async def test_set_lock_credential_rfid_too_long(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects RFID data above max byte length."""
    # "AABBCCDDEEFF0011" = 8 bytes, max is 6
    with pytest.raises(
        ServiceValidationError, match="RFID data length must be between"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "rfid",
                ATTR_CREDENTIAL_DATA: "AABBCCDDEEFF0011",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_RFID}])
async def test_clear_lock_credential_rfid(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_credential with RFID type."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    await hass.services.async_call(
        DOMAIN,
        "clear_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "rfid",
            ATTR_CREDENTIAL_INDEX: 3,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.ClearCredential(
            credential=clusters.DoorLock.Structs.CredentialStruct(
                credentialType=clusters.DoorLock.Enums.CredentialTypeEnum.kRfid,
                credentialIndex=3,
            ),
        ),
        timed_request_timeout_ms=10000,
    )


# --- CLEAR_ALL_INDEX tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_user_clear_all(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_user with CLEAR_ALL_INDEX clears all users."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    await hass.services.async_call(
        DOMAIN,
        "clear_lock_user",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: CLEAR_ALL_INDEX,
        },
        blocking=True,
    )

    # ClearUser handles credential cleanup per the Matter spec
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.ClearUser(userIndex=CLEAR_ALL_INDEX),
        timed_request_timeout_ms=10000,
    )


# --- SetCredential status code tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
@pytest.mark.parametrize(
    ("status_code", "expected_match"),
    [
        (1, "failure"),  # kFailure
        (3, "occupied"),  # kOccupied
        (99, "unknown\\(99\\)"),  # Unknown status code
    ],
)
async def test_set_lock_credential_status_codes(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    status_code: int,
    expected_match: str,
) -> None:
    """Test set_lock_credential raises error for non-success status codes."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus: empty
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": 2,
            },
            # SetCredential response with non-success status
            {"status": status_code, "userIndex": None, "nextCredentialIndex": None},
        ]
    )

    with pytest.raises(HomeAssistantError, match=expected_match):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


# --- Node event edge case tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_lock_operation_event_missing_operation_source(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test LockOperation event with missing operationSource uses Unknown."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,  # LockOperation
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={},  # No operationSource key
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes[ATTR_CHANGED_BY] == "Unknown"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_lock_operation_event_null_data(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test LockOperation event with None data uses Unknown."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,  # LockOperation
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes[ATTR_CHANGED_BY] == "Unknown"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_lock_operation_event_unknown_source(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test LockOperation event with unknown operationSource value."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,  # LockOperation
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 999},  # Unknown source
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes[ATTR_CHANGED_BY] == "Unknown"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_non_lock_operation_event_ignored(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test non-LockOperation events on the DoorLock cluster are ignored."""
    state = hass.states.get("lock.mock_door_lock")
    original_changed_by = state.attributes.get(ATTR_CHANGED_BY)

    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=99,  # Not LockOperation (event_id=2)
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 7},
        ),
    )

    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes.get(ATTR_CHANGED_BY) == original_changed_by


# --- get_lock_info edge case tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_get_lock_info_without_usr_feature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_info on lock without USR returns None for capacity fields."""
    # Default mock_door_lock has featuremap=0 (no USR)
    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_info",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"] == {
        "supports_user_management": False,
        "supported_credential_types": [],
        "max_users": None,
        "max_pin_users": None,
        "max_rfid_users": None,
        "max_credentials_per_user": None,
        "min_pin_length": None,
        "max_pin_length": None,
        "min_rfid_length": None,
        "max_rfid_length": None,
    }


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_get_lock_info_with_multiple_credential_types(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_info reports multiple supported credential types."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_lock_info",
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    info = result["lock.mock_door_lock"]
    assert info["supports_user_management"] is True
    assert "pin" in info["supported_credential_types"]
    assert "rfid" in info["supported_credential_types"]


# --- PIN boundary validation tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_pin_too_long(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential rejects PIN exceeding max length."""
    with pytest.raises(ServiceValidationError, match="PIN length must be between"):
        await hass.services.async_call(
            DOMAIN,
            "set_lock_credential",
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "123456789",  # 9 digits, max is 8
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_pin_exact_min_length(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential accepts PIN at exact minimum length."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"credentialExists": False, "userIndex": None, "nextCredentialIndex": 2},
            {"status": 0, "userIndex": 1, "nextCredentialIndex": 2},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "1234",  # Exactly 4 digits (min)
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"]["credential_index"] == 1


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_pin_exact_max_length(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential accepts PIN at exact maximum length."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"credentialExists": False, "userIndex": None, "nextCredentialIndex": 2},
            {"status": 0, "userIndex": 1, "nextCredentialIndex": 2},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "12345678",  # Exactly 8 digits (max)
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result["lock.mock_door_lock"]["credential_index"] == 1


# --- set_lock_credential with user_status and user_type params ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/257/65532": _FEATURE_USR_PIN,
            "1/257/24": 4,  # MinPINCodeLength
            "1/257/23": 8,  # MaxPINCodeLength
        }
    ],
)
async def test_set_lock_credential_with_user_status_and_type(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential passes user_status and user_type to command."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"credentialExists": False, "userIndex": None, "nextCredentialIndex": 2},
            {"status": 0, "userIndex": 1, "nextCredentialIndex": 2},
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "set_lock_credential",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "1234",
            ATTR_CREDENTIAL_INDEX: 1,
            ATTR_USER_STATUS: "occupied_disabled",
            ATTR_USER_TYPE: "non_access_user",
        },
        blocking=True,
        return_response=True,
    )

    # Verify SetCredential was called with resolved user_status and user_type
    set_cred_call = matter_client.send_device_command.call_args_list[1]
    assert (
        set_cred_call.kwargs["command"].userStatus
        == clusters.DoorLock.Enums.UserStatusEnum.kOccupiedDisabled
    )
    assert (
        set_cred_call.kwargs["command"].userType
        == clusters.DoorLock.Enums.UserTypeEnum.kNonAccessUser
    )


# --- set_lock_user with explicit params tests ---


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_new_with_explicit_params(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user creates new user with explicit type and credential rule."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser(1): empty slot
            None,  # SetUser: success
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "set_lock_user",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_NAME: "Restricted",
            ATTR_USER_TYPE: "week_day_schedule_user",
            ATTR_CREDENTIAL_RULE: "dual",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    set_user_cmd = matter_client.send_device_command.call_args_list[1]
    assert set_user_cmd == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd,
            userIndex=1,
            userName="Restricted",
            userUniqueID=None,
            userStatus=clusters.DoorLock.Enums.UserStatusEnum.kOccupiedEnabled,
            userType=clusters.DoorLock.Enums.UserTypeEnum.kWeekDayScheduleUser,
            credentialRule=clusters.DoorLock.Enums.CredentialRuleEnum.kDual,
        ),
        timed_request_timeout_ms=10000,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_update_with_explicit_type_and_rule(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user updates existing user with explicit type and rule."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # GetUser: existing user
                "userStatus": 1,
                "userName": "Old Name",
                "userUniqueID": 42,
                "userType": 0,  # kUnrestrictedUser
                "credentialRule": 0,  # kSingle
                "credentials": None,
            },
            None,  # SetUser: modify
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        "set_lock_user",
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 3,
            ATTR_USER_TYPE: "programming_user",
            ATTR_CREDENTIAL_RULE: "tri",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    set_user_cmd = matter_client.send_device_command.call_args_list[1]
    assert set_user_cmd == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetUser(
            operationType=clusters.DoorLock.Enums.DataOperationTypeEnum.kModify,
            userIndex=3,
            userName="Old Name",  # Preserved
            userUniqueID=42,  # Preserved
            userStatus=1,  # Preserved
            userType=clusters.DoorLock.Enums.UserTypeEnum.kProgrammingUser,
            credentialRule=clusters.DoorLock.Enums.CredentialRuleEnum.kTri,
        ),
        timed_request_timeout_ms=10000,
    )
