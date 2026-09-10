"""Tests for ESPHome websocket API."""

from aioesphomeapi import APIClient
from aioesphomeapi.model import SerialProxyInfo, SerialProxyPortType, SubDeviceInfo

from homeassistant.components.esphome.const import CONF_NOISE_PSK, DOMAIN
from homeassistant.components.esphome.serial_proxy import build_url
from homeassistant.components.esphome.websocket_api import DEVICE_ID, ENTRY_ID, TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MockESPHomeDeviceType

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


def _device_id_for_mac(
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    mac: str = "11:22:33:44:55:aa",
) -> str:
    """Return the device registry id for an ESPHome MAC."""
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
    )
    assert device is not None
    return device.id


async def test_get_encryption_key(
    mock_client: APIClient,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get encryption key."""
    mock_config_entry = init_integration

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_encryption_key",
            ENTRY_ID: mock_config_entry.entry_id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "encryption_key": mock_config_entry.data.get(CONF_NOISE_PSK)
    }


async def test_get_device_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test capabilities from cached DeviceInfo."""
    mock_client.connected_address = "192.168.1.2"
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "bluetooth_proxy_feature_flags": 1,
            "zwave_proxy_feature_flags": 1,
            "zwave_home_id": 1234567890,
            "serial_proxies": [
                SerialProxyInfo(name="uart0", port_type=SerialProxyPortType.TTL),
                SerialProxyInfo(name="amp", port_type=SerialProxyPortType.RS232),
                SerialProxyInfo(name="bus", port_type=SerialProxyPortType.RS485),
                SerialProxyInfo(name="unknown", port_type=None),
            ],
        },
    )

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "available": True,
        "bluetooth_proxy": {"supported": True},
        "zwave_proxy": {
            "supported": True,
            "home_id": 1234567890,
        },
        "serial_proxies": [
            {
                "name": "uart0",
                "port_type": "TTL",
                "url": str(build_url(device.entry.entry_id, "uart0")),
            },
            {
                "name": "amp",
                "port_type": "RS232",
                "url": str(build_url(device.entry.entry_id, "amp")),
            },
            {
                "name": "bus",
                "port_type": "RS485",
                "url": str(build_url(device.entry.entry_id, "bus")),
            },
            {
                "name": "unknown",
                "port_type": None,
                "url": str(build_url(device.entry.entry_id, "unknown")),
            },
        ],
    }


async def test_get_device_capabilities_device_not_found(
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get_device_capabilities when the device registry id is unknown."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: "not-a-device",
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["message"] == "Device not found"


async def test_get_device_capabilities_wrong_domain(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get_device_capabilities when the device is not ESPHome."""
    other_entry = MockConfigEntry(domain="switch", data={})
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
    )

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: device.id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["message"] == "Device is not an ESPHome device"


async def test_get_device_capabilities_sub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test capabilities are not exposed on ESPHome sub-devices."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "devices": [
                SubDeviceInfo(device_id=11111111, name="Motion Sensor", area_id=0),
            ],
        },
    )

    sub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_11111111"), device.entry.entry_id
    )
    assert sub_device is not None

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: sub_device.id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["message"] == "Device is not the main ESPHome device"


async def test_get_device_capabilities_unavailable(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test cached capabilities are returned when the device is unavailable."""
    mock_client.connected_address = "192.168.1.2"
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "bluetooth_proxy_feature_flags": 1,
            "zwave_proxy_feature_flags": 1,
            "zwave_home_id": 1234567890,
        },
    )
    device.entry.runtime_data.available = False

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "available": False,
        "bluetooth_proxy": {"supported": True},
        "zwave_proxy": {"supported": True, "home_id": 1234567890},
        "serial_proxies": [],
    }


async def test_get_device_capabilities_no_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a useful empty payload when cached DeviceInfo is missing."""
    device = await mock_esphome_device(mock_client=mock_client)
    device.entry.runtime_data.device_info = None

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "available": False,
        "bluetooth_proxy": {"supported": False},
        "zwave_proxy": {
            "supported": False,
            "home_id": 0,
        },
        "serial_proxies": [],
    }
