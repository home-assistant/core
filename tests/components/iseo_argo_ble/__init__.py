"""Tests for the ISEO Argo BLE integration."""

from datetime import timedelta
from itertools import count

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)

MOCK_ADDRESS = "AA:BB:CC:DD:EE:FF"
MOCK_NAME = "ISEO Lock"
MOCK_UUID_HEX = "eaa06132486f426cb0d26c6b9b578add"
MOCK_PRIV_SCALAR = "0x" + "a" * 56  # 224-bit hex scalar
ISEO_SERVICE_UUID = "0000f000-0000-1000-8000-00805f9b34fb"

# Each advertisement needs unique content: habluetooth deduplicates by name,
# manufacturer data, service data and service UUIDs.
_adv_counter = count(1)


def _service_info(manufacturer_data: dict[int, bytes]) -> BluetoothServiceInfoBleak:
    """Return a BluetoothServiceInfoBleak for the mock lock."""
    return BluetoothServiceInfoBleak(
        name=MOCK_NAME,
        address=MOCK_ADDRESS,
        rssi=-60,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[ISEO_SERVICE_UUID],
        source="local",
        device=generate_ble_device(address=MOCK_ADDRESS, name=MOCK_NAME),
        advertisement=generate_advertisement_data(
            local_name=MOCK_NAME,
            manufacturer_data=manufacturer_data,
            service_uuids=[ISEO_SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=None,
    )


MOCK_SERVICE_INFO = _service_info({})


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the ISEO Argo BLE integration for testing."""
    config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, MOCK_SERVICE_INFO)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def inject_advertisement(hass: HomeAssistant) -> None:
    """Inject a fresh advertisement from the lock."""
    inject_bluetooth_service_info(hass, _service_info({next(_adv_counter): b"\x01"}))


async def trigger_poll(hass: HomeAssistant) -> None:
    """Advertise the lock and let the debounced coordinator poll run."""
    inject_advertisement(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()
