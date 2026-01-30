"""Test the Matter lock user management WebSocket API."""

from unittest.mock import AsyncMock, MagicMock

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.matter.api_base import DEVICE_ID, ID, TYPE
from homeassistant.components.matter.const import (
    ATTR_MAX_CREDENTIALS_PER_USER,
    ATTR_MAX_PIN_USERS,
    ATTR_MAX_RFID_USERS,
    ATTR_MAX_USERS,
    ATTR_PIN_CODE,
    ATTR_SUPPORTS_USER_MGMT,
    ATTR_USER_INDEX,
    ATTR_USER_NAME,
    ATTR_USER_TYPE,
    CLEAR_ALL_INDEX,
    CRED_TYPE_PIN,
    CRED_TYPE_RFID,
    DOMAIN,
    ERR_CREDENTIAL_NOT_SUPPORTED,
    ERR_INVALID_PIN_CODE,
    ERR_LOCK_NOT_FOUND,
    ERR_NO_AVAILABLE_CREDENTIAL_SLOTS,
    ERR_NO_AVAILABLE_SLOTS,
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


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_lock_user_disposable_type(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test set_user with disposable_user type."""
    # Empty slot, then SetUser succeeds
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser(1): empty
            None,  # SetUser: success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "OneTime",
            ATTR_USER_TYPE: "disposable_user",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 1

    # Verify SetUser was called with disposable user type (6)
    set_user_call = matter_client.send_device_command.call_args_list[1]
    cmd = set_user_call.kwargs.get("command") or set_user_call[1].get("command")
    assert cmd.userType == 6


# --- Set user with PIN credential ---


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_with_pin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test creating a user with a PIN in one call."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser(1): empty slot
            None,  # SetUser: success
            # _get_existing_pin_credential_index: GetUser for credential check
            {"userStatus": 1, "credentials": None},
            # _find_available_credential_slot: GetCredentialStatus(1)
            {"credentialExists": False},
            # _set_credential_for_user: SetCredential
            {"status": 0, "nextCredentialIndex": 2},
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "Alice",
            ATTR_PIN_CODE: "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 1
    # GetUser(slot scan) + SetUser + GetUser(cred check) + GetCredentialStatus + SetCredential
    assert matter_client.send_device_command.call_count == 5


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_update_existing_pin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test replacing PIN on an existing user."""
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetUser for update check
            {
                "userIndex": 3,
                "userName": "Bob",
                "userUniqueID": None,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify): success
            # _get_existing_pin_credential_index: GetUser
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": pin_cred_type, "credentialIndex": 2},
                ],
            },
            # _set_credential_for_user: SetCredential (modify existing)
            {"status": 0, "nextCredentialIndex": 3},
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 3,
            ATTR_PIN_CODE: "87654321",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 3
    # GetUser + SetUser + GetUser(cred) + SetCredential
    assert matter_client.send_device_command.call_count == 4


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_clear_pin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test clearing PIN by passing pin_code=null."""
    pin_cred_type = clusters.DoorLock.Enums.CredentialTypeEnum.kPin
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetUser for update check
            {
                "userIndex": 3,
                "userName": "Bob",
                "userUniqueID": None,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify): success
            # _clear_pin_credentials_for_user: GetUser
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": pin_cred_type, "credentialIndex": 2},
                ],
            },
            None,  # ClearCredential: success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 3,
            ATTR_PIN_CODE: None,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"][ATTR_USER_INDEX] == 3
    # GetUser + SetUser + GetUser(cred) + ClearCredential
    assert matter_client.send_device_command.call_count == 4

    # Verify ClearCredential was called
    clear_cred_call = matter_client.send_device_command.call_args_list[3]
    cmd = clear_cred_call.kwargs.get("command") or clear_cred_call[1].get("command")
    assert isinstance(cmd, clusters.DoorLock.Commands.ClearCredential)


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_pin_too_short(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test PIN validation rejects too-short PIN."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "Short",
            ATTR_PIN_CODE: "1",  # MinPINCodeLength from fixture is 6
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_INVALID_PIN_CODE


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_pin_too_long(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test PIN validation rejects too-long PIN."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "Long",
            ATTR_PIN_CODE: "123456789",  # MaxPINCodeLength from fixture is 8
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_INVALID_PIN_CODE


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_pin_non_numeric(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test PIN validation rejects non-numeric PIN."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "Letters",
            ATTR_PIN_CODE: "abcd",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_INVALID_PIN_CODE


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR}])
async def test_set_user_pin_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test PIN credential on lock without kPinCredential returns error."""
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "NoPinLock",
            ATTR_PIN_CODE: "1234",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_CREDENTIAL_NOT_SUPPORTED


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_rollback_on_credential_failure(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test that new user is rolled back when credential operation fails."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            {"userStatus": None},  # GetUser(1): empty slot
            None,  # SetUser: success
            # _get_existing_pin_credential_index: GetUser
            {"userStatus": 1, "credentials": None},
            # _find_available_credential_slot: all 10 slots occupied
            # (NumberOfPINUsersSupported=10 in door_lock fixture)
            *[{"credentialExists": True} for _ in range(10)],
            None,  # ClearUser (rollback): success
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_NAME: "FailCred",
            ATTR_PIN_CODE: "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NO_AVAILABLE_CREDENTIAL_SLOTS

    # Verify ClearUser was called to rollback
    last_call = matter_client.send_device_command.call_args_list[-1]
    cmd = last_call.kwargs.get("command") or last_call[1].get("command")
    assert isinstance(cmd, clusters.DoorLock.Commands.ClearUser)
    assert cmd.userIndex == 1


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_set_user_no_credential_slots(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test ERR_NO_AVAILABLE_CREDENTIAL_SLOTS when all credential slots are full."""
    # Existing user (no rollback expected)
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # GetUser for update check
            {
                "userIndex": 1,
                "userName": "Existing",
                "userUniqueID": None,
                "userStatus": 1,
                "userType": 0,
                "credentialRule": 0,
            },
            None,  # SetUser (modify): success
            # _get_existing_pin_credential_index: no existing PIN
            {"userStatus": 1, "credentials": None},
            # _find_available_credential_slot: all 10 slots occupied
            # (NumberOfPINUsersSupported=10 in door_lock fixture)
            *[{"credentialExists": True} for _ in range(10)],
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 1,
            ATTR_PIN_CODE: "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NO_AVAILABLE_CREDENTIAL_SLOTS


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
    """Test clearing a user clears credentials first, then clears the user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # _clear_user_credentials: GetUser returns user with a PIN credential
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": 1, "credentialIndex": 1},
                ],
            },
            None,  # ClearCredential: success
            None,  # ClearUser: success
        ]
    )

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

    # Verify: GetUser + ClearCredential + ClearUser
    assert matter_client.send_device_command.call_count == 3

    # Verify ClearCredential was called
    clear_cred_call = matter_client.send_device_command.call_args_list[1]
    cmd = clear_cred_call.kwargs.get("command") or clear_cred_call[1].get("command")
    assert isinstance(cmd, clusters.DoorLock.Commands.ClearCredential)

    # Verify ClearUser was called last
    clear_user_call = matter_client.send_device_command.call_args_list[2]
    cmd = clear_user_call.kwargs.get("command") or clear_user_call[1].get("command")
    assert isinstance(cmd, clusters.DoorLock.Commands.ClearUser)
    assert cmd.userIndex == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_clear_lock_user_no_credentials(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test clearing a user with no credentials still works."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # _clear_user_credentials: GetUser returns user with no credentials
            {"userStatus": 1, "credentials": None},
            None,  # ClearUser: success
        ]
    )

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
    # GetUser + ClearUser (no ClearCredential needed)
    assert matter_client.send_device_command.call_count == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_clear_all_lock_users(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test clearing all users with CLEAR_ALL_INDEX clears credentials first."""
    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: CLEAR_ALL_INDEX,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]

    # Should have called ClearCredential(null) then ClearUser(CLEAR_ALL_INDEX)
    assert matter_client.send_device_command.call_count == 2

    # First call: ClearCredential with credential=None
    clear_cred_call = matter_client.send_device_command.call_args_list[0]
    cmd = clear_cred_call.kwargs.get("command") or clear_cred_call[1].get("command")
    assert isinstance(cmd, clusters.DoorLock.Commands.ClearCredential)
    assert cmd.credential is None

    # Second call: ClearUser with CLEAR_ALL_INDEX
    clear_user_call = matter_client.send_device_command.call_args_list[1]
    cmd = clear_user_call.kwargs.get("command") or clear_user_call[1].get("command")
    assert isinstance(cmd, clusters.DoorLock.Commands.ClearUser)
    assert cmd.userIndex == CLEAR_ALL_INDEX


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
@pytest.mark.parametrize("attributes", [{"1/257/65532": _FEATURE_USR_PIN_RFID}])
async def test_clear_user_cleans_credentials(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test that clear_user clears each credential before clearing the user."""
    matter_client.send_device_command = AsyncMock(
        side_effect=[
            # _clear_user_credentials: GetUser with multiple credentials
            {
                "userStatus": 1,
                "credentials": [
                    {"credentialType": 1, "credentialIndex": 1},  # PIN
                    {"credentialType": 2, "credentialIndex": 3},  # RFID
                ],
            },
            None,  # ClearCredential(PIN, 1)
            None,  # ClearCredential(RFID, 3)
            None,  # ClearUser
        ]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_user",
            DEVICE_ID: _get_device_id(device_registry),
            ATTR_USER_INDEX: 5,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    # GetUser + 2x ClearCredential + ClearUser
    assert matter_client.send_device_command.call_count == 4


# --- USR not supported (shared error path) ---


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
