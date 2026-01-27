"""Test Matter locks."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType, MatterNodeEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntityFeature, LockState
from homeassistant.const import ATTR_CODE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


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
    assert state.state == LockState.JAMMED

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
    assert state.state == LockState.JAMMED

    set_node_attribute(matter_node, 1, 257, 0, 3)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_with_unbolt")
    assert state
    assert state.state == LockState.OPEN


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_not_fully_locked_transitions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test NotFullyLocked state transitions."""
    # Set to NotFullyLocked (value 0)
    set_node_attribute(matter_node, 1, 257, 0, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.JAMMED

    # Transition from JAMMED to LOCKED
    set_node_attribute(matter_node, 1, 257, 0, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.LOCKED

    # Back to NotFullyLocked
    set_node_attribute(matter_node, 1, 257, 0, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.JAMMED

    # Transition from JAMMED to UNLOCKED
    set_node_attribute(matter_node, 1, 257, 0, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("lock.mock_door_lock")
    assert state
    assert state.state == LockState.UNLOCKED


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_event_attribution_with_user(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test lock event attribution includes user index."""
    # Test with userIndex present
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
            data={"operationSource": 3, "userIndex": 5},
        ),
    )
    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes[ATTR_CHANGED_BY] == "Keypad (User 5)"

    # Test without userIndex (backward compatible)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=1,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data={"operationSource": 7},
        ),
    )
    state = hass.states.get("lock.mock_door_lock")
    assert state.attributes[ATTR_CHANGED_BY] == "Remote"


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_set_lock_usercode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test setting a usercode on a Matter lock."""
    await hass.services.async_call(
        "matter",
        "set_lock_usercode",
        {
            "entity_id": "lock.mock_door_lock",
            "code_slot": 1,
            "usercode": "1234",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.SetPinCode(
            userIndex=0,  # code_slot 1 -> index 0 (0-based)
            userStatus=clusters.DoorLock.Enums.UserStatusEnum.kEnabled,
            userType=clusters.DoorLock.Enums.UserTypeEnum.kUnrestricted,
            pin=b"1234",
        ),
        timed_request_timeout_ms=1000,
    )


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_clear_lock_usercode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clearing a usercode on a Matter lock."""
    await hass.services.async_call(
        "matter",
        "clear_lock_usercode",
        {
            "entity_id": "lock.mock_door_lock",
            "code_slot": 3,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.ClearPinCode(
            userIndex=2,  # code_slot 3 -> index 2 (0-based)
        ),
        timed_request_timeout_ms=1000,
    )


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_get_lock_user(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test getting user info from a Matter lock."""
    # Mock the response for an existing user
    mock_response = MagicMock()
    mock_response.userName = "Test User"
    mock_response.userUniqueID = 1234
    mock_response.userStatus = 1
    mock_response.userType = 0
    mock_response.credentialRule = 0
    mock_response.nextUserIndex = 2
    matter_client.send_device_command.return_value = mock_response

    response = await hass.services.async_call(
        "matter",
        "get_lock_user",
        {
            "entity_id": "lock.mock_door_lock",
            "user_index": 1,
        },
        blocking=True,
        return_response=True,
    )
    result = response["lock.mock_door_lock"]
    assert result["exists"] is True
    assert result["user_name"] == "Test User"
    assert result["user_unique_id"] == 1234
    assert result["user_index"] == 1
    assert result["next_user_index"] == 2
    assert matter_client.send_device_command.call_count == 1
    matter_client.send_device_command.reset_mock()

    # Mock the response for a non-existing user (None response)
    matter_client.send_device_command.return_value = None

    response = await hass.services.async_call(
        "matter",
        "get_lock_user",
        {
            "entity_id": "lock.mock_door_lock",
            "user_index": 99,
        },
        blocking=True,
        return_response=True,
    )
    result = response["lock.mock_door_lock"]
    assert result["exists"] is False
    assert result["user_index"] == 99


@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_get_credential_status(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test getting credential status from a Matter lock."""
    # Mock the response for an existing credential
    mock_response = MagicMock()
    mock_response.credentialExists = True
    mock_response.userIndex = 1
    mock_response.creatorFabricIndex = 1
    mock_response.lastModifiedFabricIndex = 1
    mock_response.nextCredentialIndex = 2
    matter_client.send_device_command.return_value = mock_response

    response = await hass.services.async_call(
        "matter",
        "get_credential_status",
        {
            "entity_id": "lock.mock_door_lock",
            "credential_type": 1,
            "credential_index": 1,
        },
        blocking=True,
        return_response=True,
    )
    result = response["lock.mock_door_lock"]
    assert result["exists"] is True
    assert result["user_index"] == 1
    assert result["credential_type"] == 1
    assert result["credential_index"] == 1
    assert result["next_credential_index"] == 2
    assert matter_client.send_device_command.call_count == 1
    matter_client.send_device_command.reset_mock()

    # Mock the response for a non-existing credential (None response)
    matter_client.send_device_command.return_value = None

    response = await hass.services.async_call(
        "matter",
        "get_credential_status",
        {
            "entity_id": "lock.mock_door_lock",
            "credential_type": 1,
            "credential_index": 99,
        },
        blocking=True,
        return_response=True,
    )
    result = response["lock.mock_door_lock"]
    assert result["exists"] is False
    assert result["credential_type"] == 1
    assert result["credential_index"] == 99
