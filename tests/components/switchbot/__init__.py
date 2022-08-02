"""Tests for the switchbot integration."""
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "switchbot"

ENTRY_CONFIG = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_ADDRESS: "e7:89:43:99:99:99",
}

USER_INPUT = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
}

USER_INPUT_CURTAIN = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
}

USER_INPUT_SENSOR = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
}

USER_INPUT_UNSUPPORTED_DEVICE = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_ADDRESS: "test",
}

USER_INPUT_INVALID = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_ADDRESS: "invalid-mac",
}


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.switchbot.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict = ENTRY_CONFIG,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Switchbot integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


WOHAND_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoHand",
    manufacturer_data={89: b"\xfd`0U\x92W"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    source="local",
    advertisement=AdvertisementData(
        local_name="WoHand",
        manufacturer_data={89: b"\xfd`0U\x92W"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=BLEDevice("aa:bb:cc:dd:ee:ff", "WoHand"),
)
WOCURTAIN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoCurtain",
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={89: b"\xc1\xc7'}U\xab"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"c\xd0Y\x00\x11\x04"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    rssi=-60,
    source="local",
    advertisement=AdvertisementData(
        local_name="WoCurtain",
        manufacturer_data={89: b"\xc1\xc7'}U\xab"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"c\xd0Y\x00\x11\x04"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=BLEDevice("aa:bb:cc:dd:ee:ff", "WoCurtain"),
)

WOSENSORTH_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoSensorTH",
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={2409: b"\xda,\x1e\xb1\x86Au\x03\x00\x96\xac"},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"T\x00d\x00\x96\xac"},
    rssi=-60,
    source="local",
    advertisement=AdvertisementData(
        manufacturer_data={2409: b"\xda,\x1e\xb1\x86Au\x03\x00\x96\xac"},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"T\x00d\x00\x96\xac"},
    ),
    device=BLEDevice("aa:bb:cc:dd:ee:ff", "WoSensorTH"),
)

NOT_SWITCHBOT_INFO = BluetoothServiceInfoBleak(
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
