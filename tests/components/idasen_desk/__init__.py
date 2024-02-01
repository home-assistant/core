"""Tests for the IKEA Idasen Desk integration."""

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.idasen_desk.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

IDASEN_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Desk 1234",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=["99fa0001-338a-1024-8a49-009c0215f78a"],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Desk 1234"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)

NOT_IDASEN_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Not Desk",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Not Desk"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the IKEA Idasen Desk integration in Home Assistant."""
    entry = MockConfigEntry(
        title="Test",
        domain=DOMAIN,
        data={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
