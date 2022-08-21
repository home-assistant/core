"""Tests for the MicroBot integration."""
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "keymitt_ble"

ENTRY_CONFIG = {
    CONF_ACCESS_TOKEN: "test-token",
    CONF_ADDRESS: "e7:89:43:99:99:99",
}

USER_INPUT = {
    CONF_ACCESS_TOKEN: "test-token",
    CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
}

USER_INPUT_INVALID = {
    CONF_ACCESS_TOKEN: "test-token",
    CONF_ADDRESS: "invalid-mac",
}


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.keymitt_ble.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(
    hass: HomeAssistant,
    data: dict = ENTRY_CONFIG,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the MicroBot integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


SERVICE_INFO = BluetoothServiceInfoBleak(
    name="mibp",
    service_uuids=["00001831-0000-1000-8000-00805f9b34fb"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    source="local",
    advertisement=AdvertisementData(
        local_name="mibp",
        service_uuids=["00001831-0000-1000-8000-00805f9b34fb"],
    ),
    device=BLEDevice("aa:bb:cc:dd:ee:ff", "mibp"),
)

NOT_MICROBOT_INFO = BluetoothServiceInfoBleak(
    name="unknown",
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={},
    service_data={},
    rssi=-60,
    source="local",
    advertisement=AdvertisementData(
        manufacturer_data={},
        service_data={},
    ),
    device=BLEDevice("aa:bb:cc:dd:ee:ff", "unknown"),
)
