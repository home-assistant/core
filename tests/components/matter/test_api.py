"""Test the api module."""
from unittest.mock import MagicMock, call

from matter_server.client.models.node import MatterNode
from matter_server.common.errors import InvalidCommand, NodeCommissionFailed
import pytest

from homeassistant.components.matter.api import ID, TYPE
from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.helpers import get_node_id_from_ha_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.setup import async_setup_component

from .common import setup_integration_with_node_fixture

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(name="test_device")
async def test_device_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a test device."""
    return await setup_integration_with_node_fixture(
        hass, "color-temperature-light", matter_client
    )


def get_test_device(hass: HomeAssistant) -> DeviceEntry:
    """Get a device from the device registry."""
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_registry = dr.async_get(hass)
    return dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)[0]


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
    matter_client.commission_with_code.assert_called_once_with("12345678")

    matter_client.commission_with_code.reset_mock()
    matter_client.commission_with_code.side_effect = InvalidCommand(
        "test_id", "9", "Failed to commission"
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/commission",
            "code": "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "9"
    matter_client.commission_with_code.assert_called_once_with("12345678")


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
    matter_client.commission_on_network.assert_called_once_with(1234)

    matter_client.commission_on_network.reset_mock()
    matter_client.commission_on_network.side_effect = NodeCommissionFailed(
        "test_id", "1", "Failed to commission on network"
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/commission_on_network",
            "pin": 1234,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "1"
    matter_client.commission_on_network.assert_called_once_with(1234)


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


@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_get_fabrics(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    test_device: MatterNode,
    integration: MockConfigEntry,
) -> None:
    """Test the get fabrics command."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/get_fabrics",
            "device_id": "fake_id",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]

    device = get_test_device(hass)

    await ws_client.send_json(
        {ID: 2, TYPE: "matter/get_fabrics", "device_id": device.id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"fabric_count": 0, "fabric_limit": 16, "fabrics": []}

    node_id = await get_node_id_from_ha_device_id(hass, device.id)
    assert node_id

    matter_client.get_matter_fabrics.assert_called_once_with(node_id)
    matter_client.get_matter_fabrics.reset_mock()


@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_remove_fabric(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    matter_client: MagicMock,
    test_device: MatterNode,
    integration: MockConfigEntry,
) -> None:
    """Test the remove fabric command."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/remove_fabric",
            "device_id": "fake_id",
            "fabric_index": "fabric_test_id",
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    device = get_test_device(hass)
    fabric_index = "test_fabric_id"

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/remove_fabric",
            "device_id": device.id,
            "fabric_index": fabric_index,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    node_id = await get_node_id_from_ha_device_id(hass, device.id)
    assert node_id

    matter_client.remove_matter_fabric.assert_called_once_with(node_id, fabric_index)
    matter_client.remove_matter_fabric.reset_mock()
