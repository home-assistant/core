"""Tests for the switchbot integration."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

DOMAIN = "switchbot"

ENTRY_CONFIG = {
    CONF_ADDRESS: "e7:89:43:99:99:99",
}

USER_INPUT = {
    CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
}

USER_INPUT_UNSUPPORTED_DEVICE = {
    CONF_ADDRESS: "test",
}

USER_INPUT_INVALID = {
    CONF_ADDRESS: "invalid-mac",
}


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.switchbot.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Switchbot integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


WOHAND_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoHand",
    manufacturer_data={89: b"\xfd`0U\x92W"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoHand",
        manufacturer_data={89: b"\xfd`0U\x92W"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoHand"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOHAND_SERVICE_INFO_NOT_CONNECTABLE = BluetoothServiceInfoBleak(
    name="WoHand",
    manufacturer_data={89: b"\xfd`0U\x92W"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoHand",
        manufacturer_data={89: b"\xfd`0U\x92W"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "WoHand"),
    time=0,
    connectable=False,
    tx_power=-127,
)


WOHAND_ENCRYPTED_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoHand",
    manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"\xc8\x10\xcf"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="798A8547-2A3D-C609-55FF-73FA824B923B",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoHand",
        manufacturer_data={89: b"\xd8.\xad\xcd\r\x85"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"\xc8\x10\xcf"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("798A8547-2A3D-C609-55FF-73FA824B923B", "WoHand"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOHAND_SERVICE_ALT_ADDRESS_INFO = BluetoothServiceInfoBleak(
    name="WoHand",
    manufacturer_data={89: b"\xfd`0U\x92W"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="cc:cc:cc:cc:cc:cc",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoHand",
        manufacturer_data={89: b"\xfd`0U\x92W"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"H\x90\xd9"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "WoHand"),
    time=0,
    connectable=True,
    tx_power=-127,
)
WOCURTAIN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoCurtain",
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={89: b"\xc1\xc7'}U\xab"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"c\xd0Y\x00\x11\x04"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoCurtain",
        manufacturer_data={89: b"\xc1\xc7'}U\xab"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"c\xd0Y\x00\x11\x04"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "WoCurtain"),
    time=0,
    connectable=True,
    tx_power=-127,
)

WOSENSORTH_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoSensorTH",
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={2409: b"\xda,\x1e\xb1\x86Au\x03\x00\x96\xac"},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"T\x00d\x00\x96\xac"},
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={2409: b"\xda,\x1e\xb1\x86Au\x03\x00\x96\xac"},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"T\x00d\x00\x96\xac"},
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "WoSensorTH"),
    time=0,
    connectable=False,
    tx_power=-127,
)


WOLOCK_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoLock",
    manufacturer_data={2409: b"\xf1\t\x9fE\x1a]\xda\x83\x00 "},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"o\x80d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoLock",
        manufacturer_data={2409: b"\xf1\t\x9fE\x1a]\xda\x83\x00 "},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"o\x80d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "WoLock"),
    time=0,
    connectable=True,
    tx_power=-127,
)

NOT_SWITCHBOT_INFO = BluetoothServiceInfoBleak(
    name="unknown",
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    manufacturer_data={},
    service_data={},
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_data={},
    ),
    device=generate_ble_device("aa:bb:cc:dd:ee:ff", "unknown"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOMETERTHPC_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoTHPc",
    manufacturer_data={
        2409: b"\xb0\xe9\xfeT2\x15\xb7\xe4\x07\x9b\xa4\x007\x02\xd5\x00"
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"5\x00d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:AA",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoTHPc",
        manufacturer_data={
            2409: b"\xb0\xe9\xfeT2\x15\xb7\xe4\x07\x9b\xa4\x007\x02\xd5\x00"
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"5\x00d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:AA", "WoTHPc"),
    time=0,
    connectable=True,
    tx_power=-127,
)

WORELAY_SWITCH_1PM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="W1080000",
    manufacturer_data={2409: b"$X|\x0866G\x81\x00\x00\x001\x00\x00\x00\x00"},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"<\x00\x00\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="W1080000",
        manufacturer_data={2409: b"$X|\x0866G\x81\x00\x00\x001\x00\x00\x00\x00"},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"<\x00\x00\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "W1080000"),
    time=0,
    connectable=True,
    tx_power=-127,
)

LEAK_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Any",
    manufacturer_data={
        2409: b"\xd6407D1\x02V\x90\x00\x00\x00\x00\x1e\x05\x00\x00\x00\x00"
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"&\\x00V"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Any",
        manufacturer_data={
            2409: b"\xd6407D1\x02V\x90\x00\x00\x00\x00\x1e\x05\x00\x00\x00\x00"
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"&\\x00V"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Any"),
    time=0,
    connectable=False,
    tx_power=-127,
)
