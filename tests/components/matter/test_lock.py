"""Test Matter locks."""

from unittest.mock import AsyncMock, MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntityFeature, LockState
from homeassistant.components.matter.const import (
    ATTR_CODE_SLOT,
    ATTR_MAX_CREDENTIALS_PER_USER,
    ATTR_MAX_PIN_USERS,
    ATTR_MAX_RFID_USERS,
    ATTR_MAX_USERS,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USERCODE,
    DOMAIN,
    EVENT_LOCK_DISPOSABLE_USER_DELETED,
    EVENT_LOCK_OPERATION,
    SERVICE_CLEAR_LOCK_USER,
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_GET_LOCK_INFO,
    SERVICE_GET_LOCK_USERS,
    SERVICE_SET_LOCK_USER,
    SERVICE_SET_LOCK_USERCODE,
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

from tests.common import async_capture_events

# Feature map bits
_FEATURE_USR = 256  # kUser (bit 8)
_FEATURE_PIN = 1  # kPinCredential (bit 0)
_FEATURE_USR_PIN = _FEATURE_USR | _FEATURE_PIN  # 257


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


# --- Entity service tests ---


@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode service creates user and sets PIN."""
    # GetUser(1): empty slot → SetUser → GetUser(check creds): no creds →
    # GetCredentialStatus(1): available → SetCredential
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: empty
            None,  # SetUser: success
            {"userStatus": 1, "credentials": None},  # GetUser: check creds
            {"credentialExists": False},  # GetCredentialStatus: available
            {"status": 0, "nextCredentialIndex": 2},  # SetCredential
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USERCODE,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CODE_SLOT: 1,
            ATTR_USERCODE: "12345678",
        },
        blocking=True,
    )

    # GetUser + SetUser + GetUser(cred check) + GetCredentialStatus + SetCredential
    assert matter_client.send_device_command.call_count == 5


@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode_invalid_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode rejects invalid PIN."""
    with pytest.raises(HomeAssistantError, match="PIN code must be"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USERCODE,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CODE_SLOT: 1,
                ATTR_USERCODE: "12",  # Too short (min is 6)
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_set_lock_usercode_not_supported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode on lock without USR feature."""
    # Default door_lock fixture has featuremap=0, no USR support
    with pytest.raises(HomeAssistantError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USERCODE,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CODE_SLOT: 1,
                ATTR_USERCODE: "12345678",
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode_existing_user(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode updates PIN on existing user."""
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": 1},  # GetUser: existing user
            # GetUser(cred check): has PIN
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": pin_cred_type, "credentialIndex": 2},
                ],
            },
            {"status": 0, "nextCredentialIndex": 3},  # SetCredential (modify)
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USERCODE,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CODE_SLOT: 1,
            ATTR_USERCODE: "12345678",
        },
        blocking=True,
    )

    # GetUser + GetUser(cred check) + SetCredential
    assert matter_client.send_device_command.call_count == 3


@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_usercode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_usercode clears credentials and user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": 1},  # GetUser: exists
            # clear_user_credentials: GetUser returns user with PIN
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": 1, "credentialIndex": 1},
                ],
            },
            None,  # ClearCredential
            None,  # ClearUser
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_LOCK_USERCODE,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_CODE_SLOT: 1,
        },
        blocking=True,
    )

    # GetUser + GetUser(creds) + ClearCredential + ClearUser
    assert matter_client.send_device_command.call_count == 4


@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_usercode_not_found(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_usercode on empty slot raises error."""
    matter_client.send_device_command = AsyncMock(return_value={"userStatus": None})

    with pytest.raises(HomeAssistantError, match="is empty"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LOCK_USERCODE,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CODE_SLOT: 5,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["door_lock"])
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


@pytest.mark.parametrize("node_fixture", ["door_lock"])
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


@pytest.mark.parametrize("node_fixture", ["door_lock"])
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


@pytest.mark.parametrize("node_fixture", ["door_lock"])
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


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_service_on_lock_without_user_management(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test entity services on lock without USR feature raise error."""
    # Default door_lock fixture has featuremap=0, no USR support
    with pytest.raises(HomeAssistantError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "Test",
            },
            blocking=True,
        )

    with pytest.raises(HomeAssistantError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_INDEX: 1,
            },
            blocking=True,
        )
