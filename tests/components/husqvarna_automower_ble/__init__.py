"""Tests for the Husqvarna Automower Bluetooth integration."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

AUTOMOWER_SERVICE_INFO = BluetoothServiceInfo(
    name="305",
    address="00000000-0000-0000-0000-000000000003",
    rssi=-63,
    service_data={},
    manufacturer_data={1062: b"\x05\x04\xbf\xcf\xbb\r"},
    service_uuids=[
        "98bd0001-0b0e-421a-84e5-ddbf75dc6de4",
        "00001800-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
)

AUTOMOWER_UNNAMED_SERVICE_INFO = BluetoothServiceInfo(
    name=None,
    address="00000000-0000-0000-0000-000000000004",
    rssi=-63,
    service_data={},
    manufacturer_data={1062: b"\x05\x04\xbf\xcf\xbb\r"},
    service_uuids=[
        "98bd0001-0b0e-421a-84e5-ddbf75dc6de4",
        "00001800-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
)

AUTOMOWER_MISSING_MANUFACTURER_DATA_SERVICE_INFO = BluetoothServiceInfo(
    name="Missing Manufacturer Data",
    address="00000000-0000-0000-0002-000000000001",
    rssi=-63,
    service_data={},
    manufacturer_data={},
    service_uuids=[
        "98bd0001-0b0e-421a-84e5-ddbf75dc6de4",
        "00001800-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
)

AUTOMOWER_UNSUPPORTED_GROUP_SERVICE_INFO = BluetoothServiceInfo(
    name="Unsupported Group",
    address="00000000-0000-0000-0002-000000000002",
    rssi=-63,
    service_data={},
    manufacturer_data={1062: b"\x05\x04\xbf\xcf\xbb\r"},
    service_uuids=[
        "98bd0001-0b0e-421a-84e5-ddbf75dc6de4",
    ],
    source="local",
)


async def setup_entry(
    hass: HomeAssistant, mock_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Make sure the device is available."""

    inject_bluetooth_service_info(hass, AUTOMOWER_SERVICE_INFO)

    with patch("homeassistant.components.husqvarna_automower_ble.PLATFORMS", platforms):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
