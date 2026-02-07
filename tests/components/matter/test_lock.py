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
    ATTR_CODE_SLOT,
    ATTR_MAX_USERS,
    ATTR_PIN_CODE,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USERCODE,
    DOMAIN,
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode_invalid_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode rejects invalid PIN."""
    with pytest.raises(ServiceValidationError, match="PIN code must be"):
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_set_lock_usercode_not_supported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode on lock without USR feature."""
    # Default door_lock fixture has featuremap=0, no USR support
    with pytest.raises(ServiceValidationError, match="does not support"):
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_usercode_not_found(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_usercode on empty slot raises error."""
    matter_client.send_device_command = AsyncMock(return_value={"userStatus": None})

    with pytest.raises(ServiceValidationError, match="is empty"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LOCK_USERCODE,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CODE_SLOT: 5,
            },
            blocking=True,
        )


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
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode_no_available_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode when no credential slots are available."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: empty slot
            None,  # SetUser: success
            {"userStatus": 1, "credentials": None},  # GetUser: check creds (no PIN)
            {"credentialExists": True},  # GetCredentialStatus: slot 1 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 2 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 3 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 4 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 5 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 6 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 7 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 8 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 9 taken
            {"credentialExists": True},  # GetCredentialStatus: slot 10 taken
        ]
    )

    with pytest.raises(ServiceValidationError, match="No available credential slots"):
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode_credential_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode when SetCredential fails."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: empty slot
            None,  # SetUser: success
            {"userStatus": 1, "credentials": None},  # GetUser: check creds
            {"credentialExists": False},  # GetCredentialStatus: available
            {"status": "failure", "nextCredentialIndex": None},  # SetCredential: fail
        ]
    )

    with pytest.raises(HomeAssistantError, match="Failed to set credential"):
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_usercode_validation_errors_are_service_validation(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that user-caused errors raise ServiceValidationError."""
    # Test invalid PIN raises ServiceValidationError specifically
    with pytest.raises(ServiceValidationError, match="PIN code must be"):
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_service_errors_are_service_validation_for_unsupported_feature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that unsupported feature errors raise ServiceValidationError."""
    # Default door_lock fixture has featuremap=0, no USR support
    with pytest.raises(ServiceValidationError, match="does not support"):
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


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_clear_lock_usercode_empty_slot_raises_service_validation(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that clearing an empty slot raises ServiceValidationError."""
    matter_client.send_device_command = AsyncMock(
        return_value={"userStatus": None}  # GetUser: empty slot
    )

    with pytest.raises(ServiceValidationError, match="is empty"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LOCK_USERCODE,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CODE_SLOT: 1,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_no_credential_slot_raises_service_validation(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that no available credential slot raises ServiceValidationError."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: empty slot
            None,  # SetUser: success
            {"userStatus": 1, "credentials": None},  # GetUser: check creds
            {"credentialExists": True},  # slots 1-10 all taken
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
        ]
    )

    with pytest.raises(ServiceValidationError, match="No available credential slots"):
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
async def test_set_lock_usercode_with_non_digit_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_usercode rejects non-digit PIN."""
    with pytest.raises(ServiceValidationError, match="PIN code must be"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USERCODE,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_CODE_SLOT: 1,
                ATTR_USERCODE: "12AB34",  # Contains non-digits
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_with_pin_and_new_user(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user service with PIN for new user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: find empty slot (index 1)
            None,  # SetUser: create user
            {"credentials": None},  # _get_existing_pin_credential_index
            {"credentialExists": False},  # find_available_credential_slot
            {"status": 0, "nextCredentialIndex": 2},  # SetCredential
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_NAME: "Test User",
            ATTR_PIN_CODE: "12345678",
        },
        blocking=True,
    )

    # Should have called SetUser and SetCredential
    assert matter_client.send_device_command.call_count >= 4


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
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR}])
async def test_set_lock_user_pin_not_supported(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user with PIN on lock without PIN support."""
    with pytest.raises(ServiceValidationError, match="does not support PIN"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "Test User",
                ATTR_PIN_CODE: "12345678",
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_invalid_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user with invalid PIN code."""
    with pytest.raises(ServiceValidationError, match="PIN code must be"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "Test User",
                ATTR_PIN_CODE: "12",  # Too short
            },
            blocking=True,
        )


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
async def test_clear_user_credentials_no_credentials(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clear_lock_usercode when user has no credentials."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": 1},  # GetUser: user exists
            {"userStatus": 1, "credentials": None},  # clear_user_credentials: no creds
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

    # GetUser + GetUser (clear_user_credentials) + ClearUser = 3 calls
    assert matter_client.send_device_command.call_count == 3


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_clear_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user clearing PIN by passing null pin_code."""
    # User exists with a PIN, we pass pin_code=None to clear it
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # GetUser: existing user
                "userStatus": 1,
                "userName": "Test User",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify)
            {  # GetUser for _clear_pin_credentials_for_user
                "userStatus": 1,
                "credentials": [
                    {"credentialType": pin_cred_type, "credentialIndex": 1},
                ],
            },
            None,  # ClearCredential
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Test User",
            ATTR_PIN_CODE: None,  # Clear PIN
        },
        blocking=True,
    )

    # Verify ClearCredential was called
    calls = matter_client.send_device_command.call_args_list
    assert len(calls) == 4
    # Last call before ClearUser should be ClearCredential
    clear_call = calls[3]
    assert "ClearCredential" in str(clear_call)


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_clear_pin_no_existing_credentials(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user clearing PIN when user has no credentials."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # GetUser: existing user
                "userStatus": 1,
                "userName": "Test User",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify)
            {  # GetUser for _clear_pin_credentials_for_user
                "userStatus": 1,
                "credentials": None,  # No credentials
            },
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Test User",
            ATTR_PIN_CODE: None,  # Clear PIN
        },
        blocking=True,
    )

    # Only 3 calls - no ClearCredential since there are no credentials
    assert matter_client.send_device_command.call_count == 3


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_update_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user updating PIN for existing user with PIN."""
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # GetUser: existing user
                "userStatus": 1,
                "userName": "Test User",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify)
            {  # GetUser for _get_existing_pin_credential_index
                "credentials": [
                    {"credentialType": pin_cred_type, "credentialIndex": 2},
                ],
            },
            {"status": 0, "nextCredentialIndex": 3},  # SetCredential (modify)
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Test User",
            ATTR_PIN_CODE: "12345678",  # New PIN
        },
        blocking=True,
    )

    # Should use kModify for existing credential
    calls = matter_client.send_device_command.call_args_list
    assert len(calls) == 4
    # SetCredential call should be with kModify operation
    set_cred_call = calls[3]
    assert "SetCredential" in str(set_cred_call)


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_rollback_on_credential_set_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user rolls back new user on SetCredential failure."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: find empty slot (index 1)
            None,  # SetUser: create user
            {"credentials": None},  # _get_existing_pin_credential_index
            {"credentialExists": False},  # find_available_credential_slot
            {"status": 2, "nextCredentialIndex": None},  # SetCredential: FAILURE
            None,  # ClearUser (rollback)
        ]
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "New User",
                ATTR_PIN_CODE: "12345678",
            },
            blocking=True,
        )

    # Verify ClearUser was called for rollback
    calls = matter_client.send_device_command.call_args_list
    assert len(calls) == 6
    last_call = calls[5]
    assert "ClearUser" in str(last_call)


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_set_lock_user_rollback_on_no_credential_slot(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user rolls back new user when no credential slots available."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: find empty slot (index 1)
            None,  # SetUser: create user
            {"credentials": None},  # _get_existing_pin_credential_index
            # All credential slots taken (max_pin_slots=10 from fixture)
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            {"credentialExists": True},
            None,  # ClearUser (rollback)
        ]
    )

    with pytest.raises(ServiceValidationError, match="No available credential slots"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK_USER,
            {
                ATTR_ENTITY_ID: "lock.mock_door_lock",
                ATTR_USER_NAME: "New User",
                ATTR_PIN_CODE: "12345678",
            },
            blocking=True,
        )

    # Verify ClearUser was called for rollback
    calls = matter_client.send_device_command.call_args_list
    # Last call should be ClearUser
    last_call = calls[-1]
    assert "ClearUser" in str(last_call)


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR}])
async def test_set_lock_user_clear_pin_no_pin_feature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test set_lock_user clearing PIN when lock has no PIN feature - no-op."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {  # GetUser: existing user
                "userStatus": 1,
                "userName": "Test User",
                "userUniqueID": None,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify)
        ]
    )

    # This should not raise even though pin_code=None passed
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_LOCK_USER,
        {
            ATTR_ENTITY_ID: "lock.mock_door_lock",
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Test User",
            ATTR_PIN_CODE: None,  # Clear PIN - but no PIN feature, so no-op
        },
        blocking=True,
    )

    # Only 2 calls - GetUser + SetUser, no credential operations
    assert matter_client.send_device_command.call_count == 2


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN}])
async def test_get_lock_info_with_schedule_features(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_lock_info returns schedule support info."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_LOCK_INFO,
        {ATTR_ENTITY_ID: "lock.mock_door_lock"},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    # Result is keyed by entity_id
    lock_info = result["lock.mock_door_lock"]
    # Check schedule support fields are present
    assert "supports_week_day_schedules" in lock_info
    assert "supports_year_day_schedules" in lock_info
    assert "supports_holiday_schedules" in lock_info
    assert "max_week_day_schedules_per_user" in lock_info
    assert "max_year_day_schedules_per_user" in lock_info
    assert "max_holiday_schedules" in lock_info


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
