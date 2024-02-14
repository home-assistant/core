"""Tests for ESPHomeClient."""
from __future__ import annotations

from aioesphomeapi import APIClient, APIVersion, BluetoothProxyFeature, DeviceInfo
from bleak.exc import BleakError
from bleak_esphome.backend.cache import ESPHomeBluetoothCache
from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner
import pytest

from homeassistant.components.bluetooth import HaBluetoothConnector
from homeassistant.core import HomeAssistant

from tests.components.bluetooth import generate_ble_device

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


@pytest.fixture(name="client_data")
async def client_data_fixture(
    hass: HomeAssistant, mock_client: APIClient
) -> ESPHomeClientData:
    """Return a client data fixture."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    return ESPHomeClientData(
        bluetooth_device=ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS),
        cache=ESPHomeBluetoothCache(),
        client=mock_client,
        device_info=DeviceInfo(
            mac_address=ESP_MAC_ADDRESS,
            name=ESP_NAME,
            bluetooth_proxy_feature_flags=BluetoothProxyFeature.PASSIVE_SCAN
            | BluetoothProxyFeature.ACTIVE_CONNECTIONS
            | BluetoothProxyFeature.REMOTE_CACHING
            | BluetoothProxyFeature.PAIRING
            | BluetoothProxyFeature.CACHE_CLEARING
            | BluetoothProxyFeature.RAW_ADVERTISEMENTS,
        ),
        api_version=APIVersion(1, 9),
        title=ESP_NAME,
        scanner=ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True),
    )


async def test_client_usage_while_not_connected(client_data: ESPHomeClientData) -> None:
    """Test client usage while not connected."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    client = ESPHomeClient(ble_device, client_data=client_data)
    with pytest.raises(
        BleakError, match=f"{ESP_NAME}.*{ESP_MAC_ADDRESS}.*not connected"
    ):
        await client.write_gatt_char("test", b"test") is False
