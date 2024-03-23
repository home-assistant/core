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

from homeassistant.components.matter.api import (
    DEVICE_ID,
    ERROR_NODE_NOT_FOUND,
    ID,
    TYPE,
)
from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_integration_with_node_fixture

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_node_diagnostics(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
) -> None:
    """Test the node diagnostics command."""
    # setup (mock) integration with a random node fixture
    await setup_integration_with_node_fixture(
        hass,
        "onoff-light",
        matter_client,
    )
    # get the device registry entry for the mocked node
    dev_reg = dr.async_get(hass)
    entry = dev_reg.async_get_device(
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
    new_entry = dev_reg.async_get_or_create(
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_ping_node(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
) -> None:
    """Test the ping_node command."""
    # setup (mock) integration with a random node fixture
    await setup_integration_with_node_fixture(
        hass,
        "onoff-light",
        matter_client,
    )
    # get the device registry entry for the mocked node
    dev_reg = dr.async_get(hass)
    entry = dev_reg.async_get_device(
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
    new_entry = dev_reg.async_get_or_create(
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_open_commissioning_window(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
) -> None:
    """Test the open_commissioning_window command."""
    # setup (mock) integration with a random node fixture
    await setup_integration_with_node_fixture(
        hass,
        "onoff-light",
        matter_client,
    )
    # get the device registry entry for the mocked node
    dev_reg = dr.async_get(hass)
    entry = dev_reg.async_get_device(
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
    new_entry = dev_reg.async_get_or_create(
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_remove_matter_fabric(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
) -> None:
    """Test the remove_matter_fabric command."""
    # setup (mock) integration with a random node fixture
    await setup_integration_with_node_fixture(
        hass,
        "onoff-light",
        matter_client,
    )
    # get the device registry entry for the mocked node
    dev_reg = dr.async_get(hass)
    entry = dev_reg.async_get_device(
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
    new_entry = dev_reg.async_get_or_create(
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_interview_node(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
) -> None:
    """Test the interview_node command."""
    # setup (mock) integration with a random node fixture
    await setup_integration_with_node_fixture(
        hass,
        "onoff-light",
        matter_client,
    )
    # get the device registry entry for the mocked node
    dev_reg = dr.async_get(hass)
    entry = dev_reg.async_get_device(
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
    new_entry = dev_reg.async_get_or_create(
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
