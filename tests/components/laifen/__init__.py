"""Tests for the Laifen integration."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

ADDRESS = "C0:00:00:00:12:34"
NAME = "LFTB01-P-1234"

LAIFEN_SERVICE_INFO = BluetoothServiceInfo(
    name=NAME,
    address=ADDRESS,
    rssi=-60,
    manufacturer_data={0xAA00: bytes.fromhex("3412000000c0")},
    service_data={},
    service_uuids=[],
    source="local",
)

UNSUPPORTED_SERVICE_INFO = BluetoothServiceInfo(
    name="LFTB02-S-412B",
    address="C0:00:00:00:41:2B",
    rssi=-60,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Laifen integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def wake_up(hass: HomeAssistant) -> None:
    """Let the toothbrush advertise as it does when it wakes up."""
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)
