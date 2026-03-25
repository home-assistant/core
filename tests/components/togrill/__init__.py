"""Tests for the ToGrill Bluetooth integration."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

TOGRILL_SERVICE_INFO = BluetoothServiceInfo(
    name="Pro-05",
    address="00000000-0000-0000-0000-000000000001",
    rssi=-63,
    service_data={},
    manufacturer_data={34714: b"\xd9\xe3\xbe\xf3\x00"},
    service_uuids=["0000cee0-0000-1000-8000-00805f9b34fb"],
    source="local",
)

TOGRILL_SERVICE_INFO_NO_NAME = BluetoothServiceInfo(
    name="",
    address="00000000-0000-0000-0000-000000000002",
    rssi=-63,
    service_data={},
    manufacturer_data={34714: b"\xd9\xe3\xbe\xf3\x00"},
    service_uuids=["0000cee0-0000-1000-8000-00805f9b34fb"],
    source="local",
)


async def setup_entry(
    hass: HomeAssistant, mock_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Make sure the device is available."""

    with patch("homeassistant.components.togrill._PLATFORMS", platforms):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
