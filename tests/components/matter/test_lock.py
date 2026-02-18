"""Test Matter locks."""

from unittest.mock import AsyncMock, MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntityFeature, LockState
from homeassistant.components.matter.const import (
    ATTR_CREDENTIAL_DATA,
    ATTR_CREDENTIAL_INDEX,
    ATTR_CREDENTIAL_TYPE,
    ATTR_MAX_USERS,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    DOMAIN,
    SERVICE_CLEAR_LOCK_CREDENTIAL,
    SERVICE_CLEAR_LOCK_USER,
    SERVICE_GET_LOCK_CREDENTIAL_STATUS,
    SERVICE_GET_LOCK_INFO,
    SERVICE_GET_LOCK_USERS,
    SERVICE_SET_LOCK_CREDENTIAL,
    SERVICE_SET_LOCK_USER,
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
_FEATURE_USR = 256  # kUser (bit 8)
_FEATURE_USR_PIN = _FEATURE_USR | _FEATURE_PIN  # 257


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
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_NAME: "TestUser",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2


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
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "New Name",
        },
        blocking=True,
    )

    # Should have called GetUser then SetUser
    assert matter_client.send_device_command.call_count == 2


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
            SERVICE_SET_LOCK_USER,
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
            SERVICE_SET_LOCK_USER,
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
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # clear_user_credentials: GetUser returns user with no creds
            {"userStatus": 1, "credentials": None},
            None,  # ClearUser
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_user_clears_credentials_first(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_user clears credentials before clearing user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # clear_user_credentials: GetUser returns user with credentials
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": 1, "credentialIndex": 1},
                    {"credentialType": 1, "credentialIndex": 2},
                ],
            },
            None,  # ClearCredential for first
            None,  # ClearCredential for second
            None,  # ClearUser
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
        },
        blocking=True,
    )

    # GetUser + 2 ClearCredential + ClearUser
    assert matter_client.send_device_command.call_count == 4


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
        SERVICE_GET_LOCK_INFO,
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result
    # Entity service returns dict keyed by entity_id
    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result[ATTR_SUPPORTS_USER_MGMT] is True
    assert entity_result[ATTR_MAX_USERS] == 10


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
        SERVICE_GET_LOCK_USERS,
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result
    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result["total_users"] == 1
    assert entity_result["users"][0][ATTR_USER_NAME] == "Alice"


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
            SERVICE_SET_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "Test",
            },
            blocking=True,
        )

    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LOCK_USER,
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
        SERVICE_GET_LOCK_USERS,
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    # Should have 2 users
    assert result["lock.mock_door_lock"]["total_users"] == 2
    # Should only need 2 calls (using nextUserIndex)
    assert matter_client.send_device_command.call_count == 2


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
        SERVICE_GET_LOCK_USERS,
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    # Result is keyed by entity_id
    lock_users = result["lock.mock_door_lock"]
    assert lock_users["total_users"] == 1
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
        SERVICE_GET_LOCK_USERS,
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    # Result is keyed by entity_id
    lock_users = result["lock.mock_door_lock"]
    assert lock_users["total_users"] == 1
    user = lock_users["users"][0]
    assert len(user["credentials"]) == 2
    assert user["credentials"][0]["type"] == "pin"
    assert user["credentials"][0]["index"] == 1


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_matter_error_converted_to_home_assistant_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that MatterError from helpers is converted to HomeAssistantError."""
    # Simulate a MatterError from the device command
    matter_client.send_device_command = AsyncMock(
        side_effect=MatterError("Device communication failed")
    )

    with pytest.raises(HomeAssistantError, match="Device communication failed"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_LOCK_USERS,
            {ATTR_ENTITY_ID: "lock.mock_door_lock"},
            blocking=True,
            return_response=True,
        )


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
        SERVICE_SET_LOCK_CREDENTIAL,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "1234",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result
    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result[ATTR_CREDENTIAL_INDEX] == 1
    assert entity_result[ATTR_USER_INDEX] == 1

    # Verify SetCredential was called with kModify (occupied slot)
    set_cred_call = matter_client.send_device_command.call_args_list[1]
    assert (
        set_cred_call.kwargs["command"].operationType
        == clusters.DoorLock.Enums.DataOperationTypeEnum.kModify
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
async def test_set_lock_credential_auto_find_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_credential auto-finds first available slot."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetCredentialStatus(1): occupied
            {"credentialExists": True, "userIndex": 1, "nextCredentialIndex": 2},
            # GetCredentialStatus(2): empty
            {
                "credentialExists": False,
                "userIndex": None,
                "nextCredentialIndex": 3,
            },
            # SetCredential response
            {"status": 0, "userIndex": 1, "nextCredentialIndex": 3},
        ]
    )

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_CREDENTIAL,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_DATA: "5678",
        },
        blocking=True,
        return_response=True,
    )

    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result[ATTR_CREDENTIAL_INDEX] == 2

    # Verify SetCredential was called with kAdd (empty slot)
    set_cred_call = matter_client.send_device_command.call_args_list[2]
    assert (
        set_cred_call.kwargs["command"].operationType
        == clusters.DoorLock.Enums.DataOperationTypeEnum.kAdd
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
        SERVICE_SET_LOCK_CREDENTIAL,
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

    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result[ATTR_USER_INDEX] == 3

    # Verify user_index was passed in command
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
            SERVICE_SET_LOCK_CREDENTIAL,
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
            SERVICE_SET_LOCK_CREDENTIAL,
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
            SERVICE_SET_LOCK_CREDENTIAL,
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
            SERVICE_SET_LOCK_CREDENTIAL,
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
            SERVICE_SET_LOCK_CREDENTIAL,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
            },
            blocking=True,
            return_response=True,
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
        SERVICE_CLEAR_LOCK_CREDENTIAL,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    call_kwargs = matter_client.send_device_command.call_args.kwargs
    assert isinstance(
        call_kwargs["command"], clusters.DoorLock.Commands.ClearCredential
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
        SERVICE_GET_LOCK_CREDENTIAL_STATUS,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_INDEX: 1,
        },
        blocking=True,
        return_response=True,
    )

    assert result
    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result["credential_exists"] is True
    assert entity_result[ATTR_USER_INDEX] == 2
    assert entity_result["next_credential_index"] == 3


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
        SERVICE_GET_LOCK_CREDENTIAL_STATUS,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CREDENTIAL_TYPE: "pin",
            ATTR_CREDENTIAL_INDEX: 5,
        },
        blocking=True,
        return_response=True,
    )

    entity_result = result.get("lock.mock_door_lock", result)
    assert entity_result["credential_exists"] is False
    assert entity_result[ATTR_USER_INDEX] is None


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
            SERVICE_SET_LOCK_CREDENTIAL,
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
            SERVICE_CLEAR_LOCK_CREDENTIAL,
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
            SERVICE_GET_LOCK_CREDENTIAL_STATUS,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
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
async def test_set_lock_credential_matter_error(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test MatterError from set_lock_credential is wrapped in HomeAssistantError."""
    matter_client.send_device_command = AsyncMock(
        side_effect=MatterError("Device communication failed")
    )

    with pytest.raises(HomeAssistantError, match="Device communication failed"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_CREDENTIAL,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CREDENTIAL_TYPE: "pin",
                ATTR_CREDENTIAL_DATA: "1234",
                ATTR_CREDENTIAL_INDEX: 1,
            },
            blocking=True,
            return_response=True,
        )
