"""Test the api module."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, call

from matter_server.client.exceptions import ServerVersionTooOld
from matter_server.client.models.node import (
    MatterFabricData,
    NetworkType,
    NodeDiagnostics,
    NodeType,
)
from matter_server.common.errors import InvalidCommand, NodeCommissionFailed
from matter_server.common.helpers.util import dataclass_to_dict
from matter_server.common.models import (
    CommissioningParameters,
    EventType,
    NetworkTopology,
    NetworkTopologyConnection,
    NetworkTopologyNode,
    TopologyDirectionInfo,
)
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
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
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
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
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
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
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
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
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
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
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
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
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
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
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
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
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
    matter_client.remove_matter_fabric.assert_called_once_with(30, 3)

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
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
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
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
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
    matter_client.interview_node.assert_called_once_with(30)

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


def _mock_topology() -> NetworkTopology:
    """Return a mock topology with a known node, an unknown node and a border router."""
    return NetworkTopology(
        collected_at=1767888000000,
        nodes=[
            NetworkTopologyNode(
                id="30",
                kind="matter",
                network_type="thread",
                node_id=30,
                role="router",
                available=True,
            ),
            NetworkTopologyNode(
                id="99",
                kind="matter",
                network_type="thread",
                node_id=99,
                role="end_device",
                available=True,
            ),
            NetworkTopologyNode(
                id="br_1122AABBCC334455",
                kind="border_router",
                network_type="thread",
                role="router",
                ext_address="1122AABBCC334455",
                vendor_name="Apple",
            ),
        ],
        connections=[
            NetworkTopologyConnection(
                source="30",
                target="br_1122AABBCC334455",
                network="thread",
                strength="strong",
                source_to_target=TopologyDirectionInfo(strength="strong", lqi=3),
            ),
        ],
    )


def _expected_topology(
    topology: NetworkTopology, ha_device_ids: list[str | None]
) -> dict:
    """Return the expected ws payload for the given topology."""
    expected = dataclass_to_dict(topology)
    for node, ha_device_id in zip(expected["nodes"], ha_device_ids, strict=True):
        node["ha_device_id"] = ha_device_id
    return expected


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
async def test_network_topology(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the network_topology command."""
    matter_client.server_info.schema_version = 13
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
        }
    )
    assert entry is not None

    topology = _mock_topology()
    matter_client.get_network_topology = AsyncMock(return_value=topology)

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({ID: 1, TYPE: "matter/network_topology"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    # node 30 maps to the registry device, node 99 and the border router do not
    assert msg["result"] == _expected_topology(topology, [entry.id, None, None])
    matter_client.get_network_topology.assert_called_once_with(refresh=False)

    matter_client.get_network_topology.reset_mock()
    await ws_client.send_json({ID: 2, TYPE: "matter/network_topology", "refresh": True})
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.get_network_topology.assert_called_once_with(refresh=True)


@pytest.mark.parametrize(
    "command", ["matter/network_topology", "matter/subscribe_network_topology"]
)
@pytest.mark.usefixtures("integration")
async def test_network_topology_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    command: str,
) -> None:
    """Test the topology commands against a server without topology support."""
    # the conftest default schema version (1) predates network topology
    matter_client.get_network_topology = AsyncMock()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({ID: 1, TYPE: command})
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_supported"
    matter_client.get_network_topology.assert_not_called()

    # a version mismatch raised by the client also maps to not_supported
    matter_client.server_info.schema_version = 13
    matter_client.get_network_topology.side_effect = ServerVersionTooOld(
        "Command not available due to too old server version"
    )
    await ws_client.send_json({ID: 2, TYPE: command})
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_supported"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
async def test_subscribe_network_topology(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test the subscribe_network_topology command."""
    matter_client.server_info.schema_version = 13
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-000000000000001E-MatterNodeDevice")
        }
    )
    assert entry is not None

    topology = _mock_topology()
    matter_client.get_network_topology = AsyncMock(return_value=topology)

    subscription_callback: Callable[[EventType, NetworkTopology], None] | None = None
    unsubscribe = MagicMock()

    def capture_subscription(
        callback: Callable[[EventType, NetworkTopology], None],
        event_filter: EventType | None = None,
        node_filter: int | None = None,
        attr_path_filter: str | None = None,
    ) -> MagicMock:
        nonlocal subscription_callback
        assert event_filter is EventType.NETWORK_TOPOLOGY_UPDATED
        subscription_callback = callback
        return unsubscribe

    matter_client.subscribe_events.side_effect = capture_subscription

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({ID: 1, TYPE: "matter/subscribe_network_topology"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.get_network_topology.assert_called_once_with()
    assert subscription_callback is not None

    # the initial snapshot is pushed as the first event
    msg = await ws_client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"] == _expected_topology(topology, [entry.id, None, None])

    # a topology update from the server is forwarded to the subscription
    updated = _mock_topology()
    updated.collected_at = 1767888060000
    updated.nodes = topology.nodes[:1]
    updated.connections = []
    subscription_callback(EventType.NETWORK_TOPOLOGY_UPDATED, updated)
    msg = await ws_client.receive_json()

    assert msg["type"] == "event"
    assert msg["event"] == _expected_topology(updated, [entry.id])

    await ws_client.send_json({ID: 2, TYPE: "unsubscribe_events", "subscription": 1})
    msg = await ws_client.receive_json()

    assert msg["success"]
    unsubscribe.assert_called_once_with()
