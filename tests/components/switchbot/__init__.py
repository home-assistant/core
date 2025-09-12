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


def patch_async_ble_device_from_address(return_value: BluetoothServiceInfoBleak | None):
    """Patch async ble device from address to return a given value."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


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

REMOTE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Any",
    manufacturer_data={89: b"\xaa\xbb\xcc\xdd\xee\xff"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"b V\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Any",
        manufacturer_data={89: b"\xaa\xbb\xcc\xdd\xee\xff"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"b V\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Any"),
    time=0,
    connectable=False,
    tx_power=-127,
)


WOHUB2_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoHub2",
    manufacturer_data={
        2409: b"\xe7\x06\x1dx\x99y\x00\xffg\xe2\xbf]\x84\x04\x9a,\x00",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"v\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoHub2",
        manufacturer_data={
            2409: b"\xe7\x06\x1dx\x99y\x00\xffg\xe2\xbf]\x84\x04\x9a,\x00",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"v\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoHub2"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOCURTAIN3_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoCurtain3",
    address="AA:BB:CC:DD:EE:FF",
    manufacturer_data={2409: b"\xcf;Zwu\x0c\x19\x0b\x00\x11D\x006"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"{\xc06\x00\x11D"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoCurtain3",
        manufacturer_data={2409: b"\xcf;Zwu\x0c\x19\x0b\x00\x11D\x006"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"{\xc06\x00\x11D"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoCurtain3"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOBLINDTILT_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoBlindTilt",
    address="AA:BB:CC:DD:EE:FF",
    manufacturer_data={2409: b"\xfbgA`\x98\xe8\x1d%2\x11\x84"},
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"x\x00*"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoBlindTilt",
        manufacturer_data={2409: b"\xfbgA`\x98\xe8\x1d%2\x11\x84"},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"x\x00*"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoBlindTilt"),
    time=0,
    connectable=True,
    tx_power=-127,
)


def make_advertisement(
    address: str, manufacturer_data: bytes, service_data: bytes
) -> BluetoothServiceInfoBleak:
    """Make a dummy advertisement."""
    return BluetoothServiceInfoBleak(
        name="Test Device",
        address=address,
        manufacturer_data={2409: manufacturer_data},
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": service_data},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        rssi=-60,
        source="local",
        advertisement=generate_advertisement_data(
            local_name="Test Device",
            manufacturer_data={2409: manufacturer_data},
            service_data={"00000d00-0000-1000-8000-00805f9b34fb": service_data},
            service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        ),
        device=generate_ble_device(address, "Test Device"),
        time=0,
        connectable=True,
        tx_power=-127,
    )


HUBMINI_MATTER_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="HubMini Matter",
    manufacturer_data={
        2409: b"\xe6\xa1\xcd\x1f[e\x00\x00\x00\x00\x00\x00\x14\x01\x985\x00",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"%\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="HubMini Matter",
        manufacturer_data={
            2409: b"\xe6\xa1\xcd\x1f[e\x00\x00\x00\x00\x00\x00\x14\x01\x985\x00",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"v\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "HubMini Matter"),
    time=0,
    connectable=True,
    tx_power=-127,
)


ROLLER_SHADE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="RollerShade",
    manufacturer_data={
        2409: b"\xb0\xe9\xfeT\x90\x1b,\x08\x9f\x11\x04'\x00",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b",\x00'\x9f\x11\x04"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="RollerShade",
        manufacturer_data={
            2409: b"\xb0\xe9\xfeT\x90\x1b,\x08\x9f\x11\x04'\x00",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b",\x00'\x9f\x11\x04"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "RollerShade"),
    time=0,
    connectable=True,
    tx_power=-127,
)


HUMIDIFIER_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Humidifier",
    manufacturer_data={
        741: b"\xacg\xb2\xcd\xfa\xbe",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"e\x80\x00\xf9\x80Bc\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Humidifier",
        manufacturer_data={
            741: b"\xacg\xb2\xcd\xfa\xbe",
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"e\x80\x00\xf9\x80Bc\x00"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Humidifier"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOSTRIP_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoStrip",
    address="AA:BB:CC:DD:EE:FF",
    manufacturer_data={
        2409: b'\x84\xf7\x03\xb3?\xde\x04\xe4"\x0c\x00\x00\x00\x00\x00\x00'
    },
    service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"r\x00d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoStrip",
        manufacturer_data={
            2409: b'\x84\xf7\x03\xb3?\xde\x04\xe4"\x0c\x00\x00\x00\x00\x00\x00'
        },
        service_data={"00000d00-0000-1000-8000-00805f9b34fb": b"r\x00d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoStrip"),
    time=0,
    connectable=True,
    tx_power=-127,
)


WOLOCKPRO_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoLockPro",
    manufacturer_data={2409: b"\xf7a\x07H\xe6\xe8-\x80\x00d\x00\x08"},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"$\x80d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoLockPro",
        manufacturer_data={2409: b"\xf7a\x07H\xe6\xe8-\x80\x00d\x00\x08"},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"$\x80d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoLockPro"),
    time=0,
    connectable=True,
    tx_power=-127,
)


LOCK_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="WoLock",
    manufacturer_data={2409: b"\xca\xbaP\xddv;\x03\x03\x00 "},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"o\x80d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="WoLock",
        manufacturer_data={2409: b"\xca\xbaP\xddv;\x03\x03\x00 "},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"o\x80d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "WoLock"),
    time=0,
    connectable=True,
    tx_power=-127,
)


CIRCULATOR_FAN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="CirculatorFan",
    manufacturer_data={
        2409: b"\xb0\xe9\xfeXY\xa8~LR9",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"~\x00R"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="CirculatorFan",
        manufacturer_data={
            2409: b"\xb0\xe9\xfeXY\xa8~LR9",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"~\x00R"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "CirculatorFan"),
    time=0,
    connectable=True,
    tx_power=-127,
)


K20_VACUUM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="K20 Vacuum",
    manufacturer_data={
        2409: b"\xb0\xe9\xfe\x01\xf3\x8f'\x01\x11S\x00\x10d\x0f",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b".\x00d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="K20 Vacuum",
        manufacturer_data={
            2409: b"\xb0\xe9\xfe\x01\xf3\x8f'\x01\x11S\x00\x10d\x0f",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b".\x00d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "K20 Vacuum"),
    time=0,
    connectable=True,
    tx_power=-127,
)


K10_PRO_VACUUM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="K10 Pro Vacuum",
    manufacturer_data={
        2409: b"\xb0\xe9\xfeP\x8d\x8d\x02 d",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"(\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="K10 Pro Vacuum",
        manufacturer_data={
            2409: b"\xb0\xe9\xfeP\x8d\x8d\x02 d",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"(\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "K10 Pro Vacuum"),
    time=0,
    connectable=True,
    tx_power=-127,
)


K10_VACUUM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="K10 Vacuum",
    manufacturer_data={
        2409: b"\xca8\x06\xa9_\xf1\x02 d",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"}\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="K10 Vacuum",
        manufacturer_data={
            2409: b"\xca8\x06\xa9_\xf1\x02 d",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"}\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "K10 Vacuum"),
    time=0,
    connectable=True,
    tx_power=-127,
)


K10_POR_COMBO_VACUUM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="K10 Pro Combo Vacuum",
    manufacturer_data={
        2409: b"\xb0\xe9\xfe\x01\xf4\x1d\x0b\x01\x01\xb1\x03\x118\x01",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"3\x00\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="K10 Pro Combo Vacuum",
        manufacturer_data={
            2409: b"\xb0\xe9\xfe\x01\xf4\x1d\x0b\x01\x01\xb1\x03\x118\x01",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"3\x00\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "K10 Pro Combo Vacuum"),
    time=0,
    connectable=True,
    tx_power=-127,
)


S10_VACUUM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="S10 Vacuum",
    manufacturer_data={
        2409: b"\xb0\xe9\xfe\x00\x08|\n\x01\x11\x05\x00\x10M\x02",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"z\x00\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="S10 Vacuum",
        manufacturer_data={
            2409: b"\xb0\xe9\xfe\x00\x08|\n\x01\x11\x05\x00\x10M\x02",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"z\x00\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "S10 Vacuum"),
    time=0,
    connectable=True,
    tx_power=-127,
)


HUB3_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Hub3",
    manufacturer_data={
        2409: b"\xb0\xe9\xfen^)\x00\xffh&\xd6d\x83\x03\x994\x80",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00d\x00\x10\xb9@"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Hub3",
        manufacturer_data={
            2409: b"\xb0\xe9\xfen^)\x00\xffh&\xd6d\x83\x03\x994\x80",
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00d\x00\x10\xb9@"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Hub3"),
    time=0,
    connectable=True,
    tx_power=-127,
)


LOCK_LITE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Lock Lite",
    manufacturer_data={2409: b"\xe9\xd5\x11\xb2kS\x17\x93\x08 "},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"-\x80d"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Lock Lite",
        manufacturer_data={2409: b"\xe9\xd5\x11\xb2kS\x17\x93\x08 "},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"-\x80d"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Lock Lite"),
    time=0,
    connectable=True,
    tx_power=-127,
)


LOCK_ULTRA_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Lock Ultra",
    manufacturer_data={2409: b"\xb0\xe9\xfe\xb6j=%\x8204\x00\x04"},
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x804\x00\x10\xa5\xb8"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Lock Ultra",
        manufacturer_data={2409: b"\xb0\xe9\xfe\xb6j=%\x8204\x00\x04"},
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x804\x00\x10\xa5\xb8"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Lock Ultra"),
    time=0,
    connectable=True,
    tx_power=-127,
)


AIR_PURIFIER_TBALE_PM25_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Air Purifier Table PM25",
    manufacturer_data={
        2409: b"\xf0\x9e\x9e\x96j\xd6\xa1\x81\x88\xe4\x00\x01\x95\x00\x00",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"7\x00\x00\x95-\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Air Purifier Table PM25",
        manufacturer_data={
            2409: b"\xf0\x9e\x9e\x96j\xd6\xa1\x81\x88\xe4\x00\x01\x95\x00\x00",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"7\x00\x00\x95-\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Air Purifier Table PM25"),
    time=0,
    connectable=True,
    tx_power=-127,
)


AIR_PURIFIER_PM25_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Air Purifier PM25",
    manufacturer_data={
        2409: b'\xcc\x8d\xa2\xa7\x92>\t"\x80\x000\x00\x0f\x00\x00',
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"*\x00\x00\x15\x04\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Air Purifier PM25",
        manufacturer_data={
            2409: b'\xcc\x8d\xa2\xa7\x92>\t"\x80\x000\x00\x0f\x00\x00',
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"*\x00\x00\x15\x04\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Air Purifier PM25"),
    time=0,
    connectable=True,
    tx_power=-127,
)


AIR_PURIFIER_VOC_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Air Purifier VOC",
    manufacturer_data={
        2409: b"\xcc\x8d\xa2\xa7\xe4\xa6\x0b\x83\x88d\x00\xea`\x00\x00",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"+\x00\x00\x15\x04\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Air Purifier VOC",
        manufacturer_data={
            2409: b"\xcc\x8d\xa2\xa7\xe4\xa6\x0b\x83\x88d\x00\xea`\x00\x00",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"+\x00\x00\x15\x04\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Air Purifier VOC"),
    time=0,
    connectable=True,
    tx_power=-127,
)


AIR_PURIFIER_TABLE_VOC_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Air Purifier Table VOC",
    manufacturer_data={
        2409: b"\xcc\x8d\xa2\xa7\xc1\xae\x9b\x81\x8c\xb2\x00\x01\x94\x00\x00",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"8\x00\x00\x95-\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Air Purifier Table VOC",
        manufacturer_data={
            2409: b"\xcc\x8d\xa2\xa7\xc1\xae\x9b\x81\x8c\xb2\x00\x01\x94\x00\x00",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"8\x00\x00\x95-\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Air Purifier Table VOC"),
    time=0,
    connectable=True,
    tx_power=-127,
)

EVAPORATIVE_HUMIDIFIER_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Evaporative Humidifier",
    manufacturer_data={
        2409: b"\xa0\xa3\xb3,\x9c\xe68\x86\x88\xb5\x99\x12\x10\x1b\x00\x85]",
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"#\x00\x00\x15\x1c\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Evaporative Humidifier",
        manufacturer_data={
            2409: b"\xa0\xa3\xb3,\x9c\xe68\x86\x88\xb5\x99\x12\x10\x1b\x00\x85]",
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"#\x00\x00\x15\x1c\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Evaporative Humidifier"),
    time=0,
    connectable=True,
    tx_power=-127,
)


BULB_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Bulb",
    manufacturer_data={
        2409: b"@L\xca\xa7_\x12\x02\x81\x12\x00\x00",
    },
    service_data={
        "0000fd3d-0000-1000-8000-00805f9b34fb": b"u\x00d",
    },
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Bulb",
        manufacturer_data={
            2409: b"@L\xca\xa7_\x12\x02\x81\x12\x00\x00",
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"u\x00d",
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Bulb"),
    time=0,
    connectable=True,
    tx_power=-127,
)


CEILING_LIGHT_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Ceiling Light",
    manufacturer_data={
        2409: b"\xef\xfe\xfb\x9d\x10\xfe\n\x01\x18\xf3\xa4",
    },
    service_data={
        "0000fd3d-0000-1000-8000-00805f9b34fb": b"q\x00",
    },
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Ceiling Light",
        manufacturer_data={
            2409: b"\xef\xfe\xfb\x9d\x10\xfe\n\x01\x18\xf3$",
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"q\x00",
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Ceiling Light"),
    time=0,
    connectable=True,
    tx_power=-127,
)


STRIP_LIGHT_3_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Strip Light 3",
    manufacturer_data={
        2409: b'\xc0N0\xe0U\x9a\x85\x9e"\xd0\x00\x00\x00\x00\x00\x00\x12\x91\x00',
    },
    service_data={
        "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb1"
    },
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Strip Light 3",
        manufacturer_data={
            2409: b'\xc0N0\xe0U\x9a\x85\x9e"\xd0\x00\x00\x00\x00\x00\x00\x12\x91\x00',
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb1"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Strip Light 3"),
    time=0,
    connectable=True,
    tx_power=-127,
)


FLOOR_LAMP_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Floor Lamp",
    manufacturer_data={
        2409: b'\xa0\x85\xe3e,\x06P\xaa"\xd4\x00\x00\x00\x00\x00\x00\r\x93\x00',
    },
    service_data={
        "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb0"
    },
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Floor Lamp",
        manufacturer_data={
            2409: b'\xa0\x85\xe3e,\x06P\xaa"\xd4\x00\x00\x00\x00\x00\x00\r\x93\x00',
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb0"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Floor Lamp"),
    time=0,
    connectable=True,
    tx_power=-127,
)

RGBICWW_STRIP_LIGHT_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="RGBICWW Strip Light",
    manufacturer_data={
        2409: b'(7/L\x94\xb2\x0c\x9e"\x00\x11:\x00',
    },
    service_data={
        "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb3"
    },
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="RGBICWW Strip Light",
        manufacturer_data={
            2409: b'(7/L\x94\xb2\x0c\x9e"\x00\x11:\x00',
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb3"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "RGBICWW Strip Light"),
    time=0,
    connectable=True,
    tx_power=-127,
)


RGBICWW_FLOOR_LAMP_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="RGBICWW Floor Lamp",
    manufacturer_data={
        2409: b'\xdc\x06u\xa6\xfb\xb2y\x9e"\x00\x11\xb8\x00',
    },
    service_data={
        "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb4"
    },
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="RGBICWW Floor Lamp",
        manufacturer_data={
            2409: b'\xdc\x06u\xa6\xfb\xb2y\x9e"\x00\x11\xb8\x00',
        },
        service_data={
            "0000fd3d-0000-1000-8000-00805f9b34fb": b"\x00\x00\x00\x00\x10\xd0\xb4"
        },
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "RGBICWW Floor Lamp"),
    time=0,
    connectable=True,
    tx_power=-127,
)


RELAY_SWITCH_2PM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Relay Switch 2PM",
    manufacturer_data={
        2409: b"\xc0N0\xdd\xb9\xf2\x8a\xc1\x00\x00\x00\x00\x00F\x00\x00"
    },
    service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"=\x00\x00\x00"},
    service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Relay Switch 2PM",
        manufacturer_data={
            2409: b"\xc0N0\xdd\xb9\xf2\x8a\xc1\x00\x00\x00\x00\x00F\x00\x00"
        },
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": b"=\x00\x00\x00"},
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
    ),
    device=generate_ble_device("AA:BB:CC:DD:EE:FF", "Relay Switch 2PM"),
    time=0,
    connectable=True,
    tx_power=-127,
)
