"""Tests for the ISEO Argo BLE integration."""

from unittest.mock import MagicMock

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ADDRESS = "00:15:42:AA:BB:CC"  # 00:15:42 is ISEO's OUI
MOCK_UUID_HEX = "eaa06132486f426cb0d26c6b9b578add"
MOCK_PRIV_SCALAR = "0x" + "a" * 56  # 224-bit hex scalar

# A lock advertises a 0xF0xx device-type UUID; the rest of the list carries
# protocol info and, when the feature is enabled, its system state.
ISEO_SERVICE_UUIDS = [
    "0000f001-0000-1000-8000-00805f9b34fb",
    "0000d004-0000-1000-8000-00805f9b34fb",
]

# A fake BluetoothServiceInfoBleak for testing
MOCK_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="ISEO Lock",
    address=MOCK_ADDRESS,
    rssi=-60,
    manufacturer_data={},
    service_data={},
    service_uuids=ISEO_SERVICE_UUIDS,
    source="local",
    device=MagicMock(),
    advertisement=MagicMock(),
    connectable=True,
    time=0,
    tx_power=None,
)


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the ISEO Argo BLE integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
