"""Constants for Switchbot tests."""

from habluetooth import BluetoothServiceInfoBleak
from switchbot import SwitchbotModel

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

BLUETOOTH_SERVICES = {
    SwitchbotModel.BOT: BluetoothServiceInfoBleak(
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
    ),
    SwitchbotModel.METER_PRO_C: BluetoothServiceInfoBleak(
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
    ),
    SwitchbotModel.LEAK: BluetoothServiceInfoBleak(
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
    ),
    SwitchbotModel.REMOTE: BluetoothServiceInfoBleak(
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
    ),
    SwitchbotModel.HUB2: BluetoothServiceInfoBleak(
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
    ),
    SwitchbotModel.HUBMINI_MATTER: BluetoothServiceInfoBleak(
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
    ),
}
