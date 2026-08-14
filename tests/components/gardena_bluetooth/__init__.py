"""Tests for the Gardena Bluetooth integration."""

from unittest.mock import patch

from gardena_bluetooth.parse import ManufacturerData

from homeassistant.components.gardena_bluetooth.const import CONF_PRODUCT_TYPE, DOMAIN
from homeassistant.const import CONF_ADDRESS, Platform
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

AQUA_CONTOUR_SERVICE_INFO = BluetoothServiceInfo(
    name="Aqua Contour",
    address="00000000-0000-0000-0000-000000000003",
    rssi=-63,
    service_data={},
    manufacturer_data={1062: b"\x02\x05\x00\x04\x06\x12\x10\x01"},
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

PRESSURE_TANK_SERVICE_INFO = BluetoothServiceInfo(
    name="GARDENA PTU",
    address="00000000-0000-0000-0000-000000000004",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x05\x04\x80\x20\x00\x00\x02\x05\x01\x04\x06\x11\x02\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

MISSING_PRODUCT_SERVICE_INFO = BluetoothServiceInfo(
    name="Missing Product Info",
    address="00000000-0000-0000-0000-000000000000",
    rssi=-63,
    service_data={},
    manufacturer_data={1062: b"\x05\x04\xf1b\xc1\x03"},
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


def get_config_entry(service_info: BluetoothServiceInfo) -> MockConfigEntry:
    """Construct a config entry for a given discovery."""
    mfg_bytes = service_info.manufacturer_data.get(ManufacturerData.company, b"")
    product_type = ManufacturerData.decode(mfg_bytes).product_type
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: service_info.address, CONF_PRODUCT_TYPE: product_type.name},
        unique_id=service_info.address,
        minor_version=2,
    )


async def setup_entry(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry | None = None,
    platforms: list[Platform] | None = None,
    service_info: BluetoothServiceInfo = WATER_TIMER_SERVICE_INFO,
) -> MockConfigEntry:
    """Make sure the device is available."""

    inject_bluetooth_service_info(hass, service_info)

    if platforms is None:
        platforms = []

    with patch("homeassistant.components.gardena_bluetooth.PLATFORMS", platforms):
        if mock_entry is None:
            mock_entry = get_config_entry(service_info)

        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
