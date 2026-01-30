"""Test the Matter lock user management WebSocket API."""

from unittest.mock import AsyncMock, MagicMock

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.matter.api_base import DEVICE_ID, ID, TYPE
from homeassistant.components.matter.const import (
    ATTR_CREDENTIAL_RULE,
    ATTR_MAX_CREDENTIALS_PER_USER,
    ATTR_MAX_PIN_USERS,
    ATTR_MAX_RFID_USERS,
    ATTR_MAX_USERS,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_STATUS,
    ATTR_USER_TYPE,
    ATTR_USER_UNIQUE_ID,
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    DOMAIN,
    ERR_LOCK_NOT_FOUND,
    ERR_NO_AVAILABLE_SLOTS,
    ERR_USER_ALREADY_EXISTS,
    ERR_USER_NOT_FOUND,
    ERR_USR_NOT_SUPPORTED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.typing import WebSocketGenerator

# The door_lock fixture has node_id=1, compressed_fabric_id=1234
# Device identifier: deviceid_{fabric_id_hex}-{node_id_hex}-MatterNodeDevice
DOOR_LOCK_DEVICE_ID = (
    DOMAIN,
    "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice",
)

# Feature map bits
_FEATURE_USR = 256  # kUser (bit 8)
_FEATURE_PIN = 1  # kPinCredential (bit 0)
_FEATURE_RFID = 2  # kRfidCredential (bit 1)
_FEATURE_USR_PIN_RFID = _FEATURE_USR | _FEATURE_PIN | _FEATURE_RFID  # 259


# --- Helper to get device registry ID ---


def _get_device_id(device_registry: dr.DeviceRegistry) -> str:
    """Get the HA device registry ID for the door lock fixture."""
    entry = device_registry.async_get_device(identifiers={DOOR_LOCK_DEVICE_ID})
    assert entry is not None
    return entry.id


# --- Lock info ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_get_lock_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_lock_info returns capabilities and capacity."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: _get_device_id(device_registry),
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_SUPPORTS_USER_MGMT] is True
    assert CRED_TYPE_PIN in result["supported_credential_types"]
    assert CRED_TYPE_RFID in result["supported_credential_types"]
    # From the door_lock fixture attribute values
    assert result[ATTR_MAX_USERS] == 10
    assert result[ATTR_MAX_PIN_USERS] == 10
    assert result[ATTR_MAX_RFID_USERS] == 10
    assert result[ATTR_MAX_CREDENTIALS_PER_USER] == 5


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_get_lock_info_no_usr(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_lock_info when USR feature is not supported."""
    # Default door_lock fixture has featuremap=0
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: _get_device_id(device_registry),
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_SUPPORTS_USER_MGMT] is False
    # Capacity keys should not be present when USR is not supported
    assert ATTR_MAX_USERS not in result


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_get_lock_info_no_lock(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_lock_info on a non-lock device returns error."""
    ws_client = await hass_ws_client(hass)

    entry = device_registry.async_get_device(identifiers={DOOR_LOCK_DEVICE_ID})
    assert entry is not None

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_LOCK_NOT_FOUND


# --- Add user ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_add_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test adding a new user to the lock."""
    # GetUser returns empty slot, then SetUser succeeds
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser: slot empty
            None,  # SetUser: success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/add_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Alice",
            ATTR_USER_UNIQUE_ID: 12345,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 1

    # Verify two commands were sent (GetUser + SetUser)
    assert matter_client.send_device_command.call_count == 2

    # Verify SetUser was called with correct parameters
    set_user_call = matter_client.send_device_command.call_args_list[1]
    cmd = set_user_call.kwargs.get("command") or set_user_call[1].get("command")
    assert cmd.userIndex == 1
    assert cmd.userName == "Alice"
    assert cmd.userUniqueID == 12345


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_add_lock_user_already_exists(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test adding a user to an occupied slot returns error."""
    # GetUser returns occupied slot
    matter_client.send_device_command = AsyncMock(
        return_value={"userStatus": 1, "userName": "Existing"}
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/add_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USER_ALREADY_EXISTS


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_add_lock_user_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test adding a user to a lock without USR feature returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/add_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USR_NOT_SUPPORTED


# --- Update user ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_update_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test updating an existing user on the lock."""
    # GetUser returns existing user, then SetUser succeeds
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {
                "userIndex": 1,
                "userName": "Alice",
                "userUniqueID": 100,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser: success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/update_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Bob",
            ATTR_USER_TYPE: "week_day_schedule_user",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 1
    assert matter_client.send_device_command.call_count == 2

    # Verify SetUser was called with updated name but preserved other fields
    set_user_call = matter_client.send_device_command.call_args_list[1]
    cmd = set_user_call.kwargs.get("command") or set_user_call[1].get("command")
    assert cmd.userName == "Bob"
    assert cmd.userUniqueID == 100  # preserved from GetUser


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_update_lock_user_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test updating a user in an empty slot returns error."""
    matter_client.send_device_command = AsyncMock(return_value={"userStatus": None})

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/update_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 5,
            ATTR_USER_NAME: "Ghost",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USER_NOT_FOUND


# --- Set user (add or update) ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_lock_user_auto_slot(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test set_user auto-finds first available slot when user_index is omitted."""
    # First slot occupied, second slot empty, then SetUser succeeds
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": 1},  # GetUser(1): occupied
            {"userStatus": None},  # GetUser(2): empty
            None,  # SetUser: success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "NewUser",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    # Should have been assigned index 2 (first empty slot)
    assert msg["result"][ATTR_USER_INDEX] == 2
    assert matter_client.send_device_command.call_count == 3


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_lock_user_no_available_slots(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test set_user returns error when all user slots are occupied."""
    # All 10 slots occupied (door_lock fixture has NumberOfTotalUsersSupported=10)
    matter_client.send_device_command = AsyncMock(return_value={"userStatus": 1})

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "NoRoom",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NO_AVAILABLE_SLOTS


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_lock_user_with_index_updates_existing(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test set_user with user_index modifies an existing user."""
    # GetUser returns existing user, then SetUser succeeds
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {
                "userIndex": 3,
                "userName": "Old",
                "userUniqueID": None,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser: success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 3,
            ATTR_USER_NAME: "Updated",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 3
    assert matter_client.send_device_command.call_count == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_lock_user_with_index_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test set_user with user_index on empty slot returns error."""
    matter_client.send_device_command = AsyncMock(return_value={"userStatus": None})

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 7,
            ATTR_USER_NAME: "Missing",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USER_NOT_FOUND


# --- Get user ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_get_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test getting a single user from the lock."""
    matter_client.send_device_command = AsyncMock(
        return_value={
            "userIndex": 1,
            "userName": "Alice",
            "userUniqueID": 42,
            "userStatus": 1,
            "userType": 0,
            "credentialRule": 0,
            "credentials": [
                {"credentialType": 1, "credentialIndex": 1},
            ],
            "nextUserIndex": 2,
        }
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_USER_INDEX] == 1
    assert result[ATTR_USER_NAME] == "Alice"
    assert result[ATTR_USER_UNIQUE_ID] == 42
    assert result[ATTR_USER_STATUS] == "occupied_enabled"
    assert result[ATTR_USER_TYPE] == "unrestricted_user"
    assert result[ATTR_CREDENTIAL_RULE] == "single"
    assert len(result["credentials"]) == 1
    assert result["credentials"][0]["type"] == CRED_TYPE_PIN
    assert result["credentials"][0]["index"] == 1


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_get_lock_user_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test getting a user from an empty slot returns error."""
    matter_client.send_device_command = AsyncMock(return_value={"userStatus": None})

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 99,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USER_NOT_FOUND


# --- Get all users ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_get_lock_users(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test getting all users from the lock."""
    # Return two users: index 1 (occupied, nextUserIndex=3), index 3 (occupied, no next)
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
                "nextUserIndex": 3,
            },
            {
                "userIndex": 3,
                "userName": "Bob",
                "userUniqueID": None,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
                "credentials": None,
                "nextUserIndex": None,
            },
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_users",
            DEVICE_ID: _get_device_id(device_registry),
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["total_users"] == 2
    assert result[ATTR_MAX_USERS] == 10
    assert len(result["users"]) == 2
    assert result["users"][0][ATTR_USER_NAME] == "Alice"
    assert result["users"][1][ATTR_USER_NAME] == "Bob"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_get_lock_users_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test getting users from a lock with no users."""
    # First slot is empty and has no next index
    matter_client.send_device_command = AsyncMock(
        return_value={
            "userStatus": None,
            "nextUserIndex": None,
        }
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_users",
            DEVICE_ID: _get_device_id(device_registry),
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["total_users"] == 0
    assert result["users"] == []


# --- Clear user ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_clear_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clearing a user from the lock."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 2,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]

    # Verify ClearUser command was sent
    matter_client.send_device_command.assert_called_once()
    call_kwargs = matter_client.send_device_command.call_args.kwargs
    assert call_kwargs["node_id"] == matter_node.node_id
    assert call_kwargs["endpoint_id"] == 1
    assert isinstance(call_kwargs["command"], clusters.DoorLock.Commands.ClearUser)
    assert call_kwargs["command"].userIndex == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_clear_all_lock_users(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test clearing all users with the special 0xFFFE index."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 0xFFFE,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    call_kwargs = matter_client.send_device_command.call_args.kwargs
    assert call_kwargs["command"].userIndex == 0xFFFE


# --- USR not supported (shared error path) ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_get_user_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_user on a lock without USR feature returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USR_NOT_SUPPORTED


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_get_users_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_users on a lock without USR feature returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_users",
            DEVICE_ID: _get_device_id(device_registry),
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USR_NOT_SUPPORTED


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_clear_user_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test clear_user on a lock without USR feature returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USR_NOT_SUPPORTED


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_set_user_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test set_user on a lock without USR feature returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "Test",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USR_NOT_SUPPORTED


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_update_user_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test update_user on a lock without USR feature returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/update_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
            ATTR_USER_NAME: "Test",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_USR_NOT_SUPPORTED
