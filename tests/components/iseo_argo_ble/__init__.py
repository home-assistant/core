"""Tests for the ISEO Argo BLE integration."""

from unittest.mock import MagicMock

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

MOCK_ADDRESS = "AA:BB:CC:DD:EE:FF"
MOCK_UUID_HEX = "eaa06132486f426cb0d26c6b9b578add"
MOCK_PRIV_SCALAR = "0x" + "a" * 56  # 224-bit hex scalar

# A fake BluetoothServiceInfoBleak for testing
MOCK_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="ISEO Lock",
    address=MOCK_ADDRESS,
    rssi=-60,
    manufacturer_data={},
    service_data={},
    service_uuids=["0000f000-0000-1000-8000-00805f9b34fb"],
    source="local",
    device=MagicMock(),
    advertisement=MagicMock(),
    connectable=True,
    time=0,
    tx_power=None,
)
