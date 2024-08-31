"""Tests for the Gardena Bluetooth integration."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info

WATER_TIMER_SERVICE_INFO = BluetoothServiceInfo(
    name="Timer",
    address="00000000-0000-0000-0000-000000000001",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x12\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

WATER_TIMER_UNNAMED_SERVICE_INFO = BluetoothServiceInfo(
    name=None,
    address="00000000-0000-0000-0000-000000000002",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x12\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

MISSING_SERVICE_SERVICE_INFO = BluetoothServiceInfo(
    name="Missing Service Info",
    address="00000000-0000-0000-0001-000000000000",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x12\x00\x01"
    },
    service_uuids=[],
    source="local",
)

MISSING_MANUFACTURER_DATA_SERVICE_INFO = BluetoothServiceInfo(
    name="Missing Manufacturer Data",
    address="00000000-0000-0000-0001-000000000001",
    rssi=-63,
    service_data={},
    manufacturer_data={},
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

UNSUPPORTED_GROUP_SERVICE_INFO = BluetoothServiceInfo(
    name="Unsupported Group",
    address="00000000-0000-0000-0001-000000000002",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x10\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)


async def setup_entry(
    hass: HomeAssistant, mock_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Make sure the device is available."""

    inject_bluetooth_service_info(hass, WATER_TIMER_SERVICE_INFO)

    with patch("homeassistant.components.gardena_bluetooth.PLATFORMS", platforms):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
