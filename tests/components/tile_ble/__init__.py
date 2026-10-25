"""Tests for the Tile BLE integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

TILE_ADDRESS = "AA:BB:CC:DD:EE:FF"
AUTH_KEY = "AAECAwQFBgcICQoLDA0ODw=="
OTHER_AUTH_KEY = "EBESExQVFhcYGRobHB0eHw=="
TILE_SERVICE_UUID = "0000feed-0000-1000-8000-00805f9b34fb"

TILE_SERVICE_INFO = BluetoothServiceInfo(
    name="Tile",
    address=TILE_ADDRESS,
    rssi=-60,
    manufacturer_data={},
    service_data={TILE_SERVICE_UUID: b"\x02\x00\xc5\x8a\xac\xcd\x31\x2f\x47\x9e"},
    service_uuids=[TILE_SERVICE_UUID],
    source="local",
)

NEAR_TILE_SERVICE_INFO = BluetoothServiceInfo(
    name="Tile",
    address="AA:BB:CC:DD:EE:11",
    rssi=-40,
    manufacturer_data={},
    service_data={TILE_SERVICE_UUID: b"\x02\x00\x01\x02\x03\x04\x05\x06\x07\x08"},
    service_uuids=[TILE_SERVICE_UUID],
    source="local",
)

NOT_TILE_SERVICE_INFO = BluetoothServiceInfo(
    name="Not a Tile",
    address="AA:BB:CC:DD:EE:22",
    rssi=-30,
    manufacturer_data={76: b"\x02\x15"},
    service_data={},
    service_uuids=[],
    source="local",
)


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Tile BLE integration for testing."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
