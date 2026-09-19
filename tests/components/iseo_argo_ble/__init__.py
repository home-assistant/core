"""Tests for the ISEO Argo BLE integration."""

from unittest.mock import MagicMock

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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


def iseo_advertisement(door_closed: bool) -> BluetoothServiceInfoBleak:
    """Return an ISEO advertisement encoding the given door status.

    The lock encodes its state in 16-bit service UUIDs: one 0xF0xx device-type
    marker, and one 0xExxx state word whose 0x0800 bit is the door contact.
    """
    state = 0xE800 if door_closed else 0xE000
    return BluetoothServiceInfoBleak(
        name="ISEO Lock",
        address=MOCK_ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[
            "0000f001-0000-1000-8000-00805f9b34fb",
            f"0000{state:04x}-0000-1000-8000-00805f9b34fb",
        ],
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
