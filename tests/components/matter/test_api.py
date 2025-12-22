"""Test the api module."""

from unittest.mock import AsyncMock, MagicMock, call

from matter_server.client.models.node import (
    MatterFabricData,
    NetworkType,
    NodeDiagnostics,
    NodeType,
)
from matter_server.common.errors import InvalidCommand, NodeCommissionFailed
from matter_server.common.helpers.util import dataclass_to_dict
from matter_server.common.models import CommissioningParameters
import pytest

from homeassistant.components.matter.api_base import (
    DEVICE_ID,
    ERROR_NODE_NOT_FOUND,
    ID,
    TYPE,
)
from homeassistant.components.matter.api_lock import (
    ERROR_LOCK_NOT_FOUND,
    ERROR_USR_NOT_SUPPORTED,
)
from homeassistant.components.matter.api_lock_schedules import (
    ERROR_HOLIDAY_SCHEDULES_NOT_SUPPORTED,
    ERROR_INVALID_TIME_RANGE,
    ERROR_SCHEDULE_NOT_FOUND,
    ERROR_WEEK_DAY_SCHEDULES_NOT_SUPPORTED,
    ERROR_YEAR_DAY_SCHEDULES_NOT_SUPPORTED,
)
from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_commission(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the commission command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/commission",
            "code": "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.commission_with_code.assert_called_once_with("12345678", True)

    matter_client.commission_with_code.reset_mock()
    matter_client.commission_with_code.side_effect = InvalidCommand(
        "test_id", "9", "Failed to commission"
    )

    await ws_client.send_json(
        {ID: 2, TYPE: "matter/commission", "code": "12345678", "network_only": False}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "9"
    matter_client.commission_with_code.assert_called_once_with("12345678", False)


async def test_commission_on_network(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the commission on network command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/commission_on_network",
            "pin": 1234,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.commission_on_network.assert_called_once_with(1234, None)

    matter_client.commission_on_network.reset_mock()
    matter_client.commission_on_network.side_effect = NodeCommissionFailed(
        "test_id", "1", "Failed to commission on network"
    )

    await ws_client.send_json(
        {ID: 2, TYPE: "matter/commission_on_network", "pin": 1234, "ip_addr": "1.2.3.4"}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "1"
    matter_client.commission_on_network.assert_called_once_with(1234, "1.2.3.4")


async def test_set_thread_dataset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the set thread dataset command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/set_thread",
            "thread_operation_dataset": "test_dataset",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.set_thread_operational_dataset.assert_called_once_with("test_dataset")

    matter_client.set_thread_operational_dataset.reset_mock()
    matter_client.set_thread_operational_dataset.side_effect = NodeCommissionFailed(
        "test_id", "1", "Failed to commission"
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/set_thread",
            "thread_operation_dataset": "test_dataset",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "1"
    matter_client.set_thread_operational_dataset.assert_called_once_with("test_dataset")


async def test_set_wifi_credentials(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the set WiFi credentials command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/set_wifi_credentials",
            "network_name": "test_network",
            "password": "test_password",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert matter_client.set_wifi_credentials.call_count == 1
    assert matter_client.set_wifi_credentials.call_args == call(
        ssid="test_network", credentials="test_password"
    )

    matter_client.set_wifi_credentials.reset_mock()
    matter_client.set_wifi_credentials.side_effect = NodeCommissionFailed(
        "test_id", "1", "Failed to commission on network"
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/set_wifi_credentials",
            "network_name": "test_network",
            "password": "test_password",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "1"
    assert matter_client.set_wifi_credentials.call_count == 1
    assert matter_client.set_wifi_credentials.call_args == call(
        ssid="test_network", credentials="test_password"
    )


@pytest.mark.usefixtures("matter_node")
# setup (mock) integration with a random node fixture
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_node_diagnostics(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the node diagnostics command."""
    # get the device registry entry for the mocked node
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # create a mock NodeDiagnostics
    mock_diagnostics = NodeDiagnostics(
        node_id=1,
        network_type=NetworkType.WIFI,
        node_type=NodeType.END_DEVICE,
        network_name="SuperCoolWiFi",
        ip_adresses=["192.168.1.1", "fe80::260:97ff:fe02:6ea5"],
        mac_address="00:11:22:33:44:55",
        available=True,
        active_fabrics=[MatterFabricData(2, 4939, 1, vendor_name="Nabu Casa")],
        active_fabric_index=0,
    )
    matter_client.node_diagnostics = AsyncMock(return_value=mock_diagnostics)

    # issue command on the ws api
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/node_diagnostics",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["type"] == "result"
    diag_res = dataclass_to_dict(mock_diagnostics)
    # dataclass to dict allows enums which are converted to string when serializing
    diag_res["network_type"] = diag_res["network_type"].value
    diag_res["node_type"] = diag_res["node_type"].value
    assert msg["result"] == diag_res

    # repeat test with a device id that does not have a node attached
    new_entry = device_registry.async_get_or_create(
        config_entry_id=list(entry.config_entries)[0],
        identifiers={(DOMAIN, "MatterNodeDevice")},
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/node_diagnostics",
            DEVICE_ID: new_entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_NODE_NOT_FOUND


@pytest.mark.usefixtures("matter_node")
# setup (mock) integration with a random node fixture
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_ping_node(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the ping_node command."""
    # get the device registry entry for the mocked node
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # create a mocked ping result
    ping_result = {"192.168.1.1": False, "fe80::260:97ff:fe02:6ea5": True}
    matter_client.ping_node = AsyncMock(return_value=ping_result)

    # issue command on the ws api
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/ping_node",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["type"] == "result"
    assert msg["result"] == ping_result

    # repeat test with a device id that does not have a node attached
    new_entry = device_registry.async_get_or_create(
        config_entry_id=list(entry.config_entries)[0],
        identifiers={(DOMAIN, "MatterNodeDevice")},
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/ping_node",
            DEVICE_ID: new_entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_NODE_NOT_FOUND


@pytest.mark.usefixtures("matter_node")
# setup (mock) integration with a random node fixture
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_open_commissioning_window(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the open_commissioning_window command."""
    # get the device registry entry for the mocked node
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # create mocked CommissioningParameters
    commissioning_parameters = CommissioningParameters(
        setup_pin_code=51590642,
        setup_manual_code="36296231484",
        setup_qr_code="MT:00000CQM008-WE3G310",
    )
    matter_client.open_commissioning_window = AsyncMock(
        return_value=commissioning_parameters
    )

    # issue command on the ws api
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/open_commissioning_window",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["type"] == "result"
    assert msg["result"] == dataclass_to_dict(commissioning_parameters)

    # repeat test with a device id that does not have a node attached
    new_entry = device_registry.async_get_or_create(
        config_entry_id=list(entry.config_entries)[0],
        identifiers={(DOMAIN, "MatterNodeDevice")},
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/open_commissioning_window",
            DEVICE_ID: new_entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_NODE_NOT_FOUND


@pytest.mark.usefixtures("matter_node")
# setup (mock) integration with a random node fixture
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_remove_matter_fabric(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the remove_matter_fabric command."""
    # get the device registry entry for the mocked node
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # issue command on the ws api
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/remove_matter_fabric",
            DEVICE_ID: entry.id,
            "fabric_index": 3,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    matter_client.remove_matter_fabric.assert_called_once_with(1, 3)

    # repeat test with a device id that does not have a node attached
    new_entry = device_registry.async_get_or_create(
        config_entry_id=list(entry.config_entries)[0],
        identifiers={(DOMAIN, "MatterNodeDevice")},
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/remove_matter_fabric",
            DEVICE_ID: new_entry.id,
            "fabric_index": 3,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_NODE_NOT_FOUND


@pytest.mark.usefixtures("matter_node")
# setup (mock) integration with a random node fixture
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_interview_node(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the interview_node command."""
    # get the device registry entry for the mocked node
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None
    # issue command on the ws api
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {ID: 1, TYPE: "matter/interview_node", DEVICE_ID: entry.id}
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    matter_client.interview_node.assert_called_once_with(1)

    # repeat test with a device id that does not have a node attached
    new_entry = device_registry.async_get_or_create(
        config_entry_id=list(entry.config_entries)[0],
        identifiers={(DOMAIN, "MatterNodeDevice")},
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/interview_node",
            DEVICE_ID: new_entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_NODE_NOT_FOUND


# Lock Credential Management API Tests


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_get_lock_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_info command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["supports_user_management"] is True
    assert result["max_users"] == 10
    assert result["max_pin_users"] == 10
    assert result["max_rfid_users"] == 5
    assert result["max_credentials_per_user"] == 5
    assert "pin" in result["supported_credential_types"]


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_get_lock_info_no_usr_feature(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_info command for lock without USR feature."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    # Lock without USR should still return basic info
    assert result["supports_user_management"] is False
    assert "max_users" not in result


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["onoff_light"])
async def test_get_lock_info_not_a_lock(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_info command for a non-lock device."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_LOCK_NOT_FOUND


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_add_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the add_lock_user command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock GetUser response (empty slot)
    mock_get_user_response = MagicMock()
    mock_get_user_response.userStatus = None  # Empty slot
    matter_client.send_device_command = AsyncMock(return_value=mock_get_user_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/add_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
            "user_name": "Test User",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"]["user_index"] == 1
    # Verify SetUser was called
    assert matter_client.send_device_command.call_count == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_add_lock_user_slot_occupied(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the add_lock_user command when slot is already occupied."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock GetUser response (occupied slot)
    mock_get_user_response = MagicMock()
    mock_get_user_response.userStatus = 1  # Occupied
    matter_client.send_device_command = AsyncMock(return_value=mock_get_user_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/add_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
            "user_name": "Test User",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "user_already_exists"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_get_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_user command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock GetUser response
    mock_get_user_response = MagicMock()
    mock_get_user_response.userIndex = 1
    mock_get_user_response.userName = "Test User"
    mock_get_user_response.userUniqueID = 12345
    mock_get_user_response.userStatus = 1  # OccupiedEnabled
    mock_get_user_response.userType = 0  # UnrestrictedUser
    mock_get_user_response.credentialRule = 0  # Single
    mock_get_user_response.credentials = []
    mock_get_user_response.nextUserIndex = 2
    matter_client.send_device_command = AsyncMock(return_value=mock_get_user_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["user_index"] == 1
    assert result["user_name"] == "Test User"
    assert result["user_status"] == "occupied_enabled"
    assert result["user_type"] == "unrestricted_user"
    assert result["next_user_index"] == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_get_lock_user_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_user command when user doesn't exist."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock GetUser response (empty)
    mock_get_user_response = MagicMock()
    mock_get_user_response.userStatus = None
    matter_client.send_device_command = AsyncMock(return_value=mock_get_user_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "user_not_found"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_get_lock_users(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_users command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock GetUser responses - user at index 1, next is 3, then no more
    mock_user1 = MagicMock()
    mock_user1.userIndex = 1
    mock_user1.userName = "User 1"
    mock_user1.userUniqueID = 1
    mock_user1.userStatus = 1
    mock_user1.userType = 0
    mock_user1.credentialRule = 0
    mock_user1.credentials = []
    mock_user1.nextUserIndex = 3

    mock_user3 = MagicMock()
    mock_user3.userIndex = 3
    mock_user3.userName = "User 3"
    mock_user3.userUniqueID = 3
    mock_user3.userStatus = 1
    mock_user3.userType = 0
    mock_user3.credentialRule = 0
    mock_user3.credentials = []
    mock_user3.nextUserIndex = None  # No more users

    matter_client.send_device_command = AsyncMock(side_effect=[mock_user1, mock_user3])

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_users",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["total_users"] == 2
    assert result["max_users"] == 10
    assert len(result["users"]) == 2
    assert result["users"][0]["user_name"] == "User 1"
    assert result["users"][1]["user_name"] == "User 3"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_clear_lock_user(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the clear_lock_user command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.send_device_command.assert_called_once()


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_set_lock_credential(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the set_lock_credential command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock GetCredentialStatus (slot empty) and SetCredential response
    mock_status_response = MagicMock()
    mock_status_response.credentialExists = False

    mock_set_response = MagicMock()
    mock_set_response.status = 0  # Success
    mock_set_response.userIndex = 1
    mock_set_response.nextCredentialIndex = 2

    matter_client.send_device_command = AsyncMock(
        side_effect=[mock_status_response, mock_set_response]
    )

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_credential",
            DEVICE_ID: entry.id,
            "credential_type": "pin",
            "credential_index": 1,
            "credential_data": "1234",
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["status"] == "success"
    assert result["user_index"] == 1
    assert result["next_credential_index"] == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_get_lock_credential_status(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_credential_status command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    mock_status_response = MagicMock()
    mock_status_response.credentialExists = True
    mock_status_response.userIndex = 1
    mock_status_response.nextCredentialIndex = 2
    matter_client.send_device_command = AsyncMock(return_value=mock_status_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_credential_status",
            DEVICE_ID: entry.id,
            "credential_type": "pin",
            "credential_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["credential_exists"] is True
    assert result["user_index"] == 1
    assert result["next_credential_index"] == 2


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_clear_lock_credential(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the clear_lock_credential command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_credential",
            DEVICE_ID: entry.id,
            "credential_type": "pin",
            "credential_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.send_device_command.assert_called_once()


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock"])
async def test_lock_commands_usr_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test lock commands on a lock without USR feature."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)

    # Test add_user
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/add_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_USR_NOT_SUPPORTED

    # Test get_user
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/lock/get_user",
            DEVICE_ID: entry.id,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_USR_NOT_SUPPORTED

    # Test set_credential
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "matter/lock/set_credential",
            DEVICE_ID: entry.id,
            "credential_type": "pin",
            "credential_index": 1,
            "credential_data": "1234",
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_USR_NOT_SUPPORTED


# Lock Schedule Management API Tests


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_get_lock_info_with_schedules(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_lock_info command includes schedule info."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_lock_info",
            DEVICE_ID: entry.id,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    # Check schedule feature support
    assert result["supports_week_day_schedules"] is True
    assert result["supports_year_day_schedules"] is True
    assert result["supports_holiday_schedules"] is True
    # Check schedule capacity
    assert result["max_week_day_schedules_per_user"] == 10
    assert result["max_year_day_schedules_per_user"] == 10
    assert result["max_holiday_schedules"] == 10


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_set_week_day_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the set_week_day_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_week_day_schedule",
            DEVICE_ID: entry.id,
            "week_day_index": 1,
            "user_index": 1,
            "days_mask": 62,  # Monday through Friday (0b111110)
            "start_hour": 9,
            "start_minute": 0,
            "end_hour": 17,
            "end_minute": 0,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["week_day_index"] == 1
    assert result["user_index"] == 1
    matter_client.send_device_command.assert_called_once()


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_set_week_day_schedule_invalid_time_range(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the set_week_day_schedule command with invalid time range."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_week_day_schedule",
            DEVICE_ID: entry.id,
            "week_day_index": 1,
            "user_index": 1,
            "days_mask": 62,
            "start_hour": 17,
            "start_minute": 0,
            "end_hour": 9,  # End before start
            "end_minute": 0,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_INVALID_TIME_RANGE


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_get_week_day_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_week_day_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock response
    mock_response = MagicMock()
    mock_response.status = 0  # Success
    mock_response.weekDayIndex = 1
    mock_response.userIndex = 1
    mock_response.daysMask = 62
    mock_response.startHour = 9
    mock_response.startMinute = 0
    mock_response.endHour = 17
    mock_response.endMinute = 0
    matter_client.send_device_command = AsyncMock(return_value=mock_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_week_day_schedule",
            DEVICE_ID: entry.id,
            "week_day_index": 1,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["week_day_index"] == 1
    assert result["days_mask"] == 62
    assert result["days"] == ["monday", "tuesday", "wednesday", "thursday", "friday"]
    assert result["start_hour"] == 9
    assert result["end_hour"] == 17


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_get_week_day_schedule_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_week_day_schedule command when schedule not found."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # Mock response - schedule not found
    mock_response = MagicMock()
    mock_response.status = 1  # Not found
    matter_client.send_device_command = AsyncMock(return_value=mock_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_week_day_schedule",
            DEVICE_ID: entry.id,
            "week_day_index": 1,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_SCHEDULE_NOT_FOUND


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_clear_week_day_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the clear_week_day_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_week_day_schedule",
            DEVICE_ID: entry.id,
            "week_day_index": 1,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.send_device_command.assert_called_once()


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_set_year_day_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the set_year_day_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_year_day_schedule",
            DEVICE_ID: entry.id,
            "year_day_index": 1,
            "user_index": 1,
            "local_start_time": 1704067200,  # Jan 1, 2024
            "local_end_time": 1735689600,  # Jan 1, 2025
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["year_day_index"] == 1
    assert result["user_index"] == 1


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_set_year_day_schedule_invalid_time_range(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the set_year_day_schedule command with invalid time range."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_year_day_schedule",
            DEVICE_ID: entry.id,
            "year_day_index": 1,
            "user_index": 1,
            "local_start_time": 1735689600,  # Jan 1, 2025
            "local_end_time": 1704067200,  # Jan 1, 2024 (before start)
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_INVALID_TIME_RANGE


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_get_year_day_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_year_day_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    mock_response = MagicMock()
    mock_response.status = 0
    mock_response.yearDayIndex = 1
    mock_response.userIndex = 1
    mock_response.localStartTime = 1704067200
    mock_response.localEndTime = 1735689600
    matter_client.send_device_command = AsyncMock(return_value=mock_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_year_day_schedule",
            DEVICE_ID: entry.id,
            "year_day_index": 1,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["year_day_index"] == 1
    assert result["local_start_time"] == 1704067200
    assert result["local_end_time"] == 1735689600


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_clear_year_day_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the clear_year_day_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_year_day_schedule",
            DEVICE_ID: entry.id,
            "year_day_index": 1,
            "user_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.send_device_command.assert_called_once()


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_set_holiday_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the set_holiday_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_holiday_schedule",
            DEVICE_ID: entry.id,
            "holiday_index": 1,
            "local_start_time": 1703980800,  # Dec 31, 2023
            "local_end_time": 1704153600,  # Jan 2, 2024
            "operating_mode": "vacation",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["holiday_index"] == 1


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_get_holiday_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the get_holiday_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    mock_response = MagicMock()
    mock_response.status = 0
    mock_response.holidayIndex = 1
    mock_response.localStartTime = 1703980800
    mock_response.localEndTime = 1704153600
    mock_response.operatingMode = 1  # vacation
    matter_client.send_device_command = AsyncMock(return_value=mock_response)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/get_holiday_schedule",
            DEVICE_ID: entry.id,
            "holiday_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result["holiday_index"] == 1
    assert result["operating_mode"] == "vacation"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_schedules"])
async def test_clear_holiday_schedule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the clear_holiday_schedule command."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    matter_client.send_device_command = AsyncMock(return_value=None)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/clear_holiday_schedule",
            DEVICE_ID: entry.id,
            "holiday_index": 1,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.send_device_command.assert_called_once()


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["door_lock_with_usr"])
async def test_schedule_commands_feature_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test schedule commands on a lock without schedule features."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    ws_client = await hass_ws_client(hass)

    # Test week day schedule
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/lock/set_week_day_schedule",
            DEVICE_ID: entry.id,
            "week_day_index": 1,
            "user_index": 1,
            "days_mask": 62,
            "start_hour": 9,
            "start_minute": 0,
            "end_hour": 17,
            "end_minute": 0,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_WEEK_DAY_SCHEDULES_NOT_SUPPORTED

    # Test year day schedule
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/lock/set_year_day_schedule",
            DEVICE_ID: entry.id,
            "year_day_index": 1,
            "user_index": 1,
            "local_start_time": 1704067200,
            "local_end_time": 1735689600,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_YEAR_DAY_SCHEDULES_NOT_SUPPORTED

    # Test holiday schedule
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "matter/lock/set_holiday_schedule",
            DEVICE_ID: entry.id,
            "holiday_index": 1,
            "local_start_time": 1703980800,
            "local_end_time": 1704153600,
            "operating_mode": "vacation",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERROR_HOLIDAY_SCHEDULES_NOT_SUPPORTED
