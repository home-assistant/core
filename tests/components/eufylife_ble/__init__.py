"""Tests for the EufyLife integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_EUFYLIFE_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="11:22:33:44:55:66",
    rssi=-60,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)

T9146_SERVICE_INFO = BluetoothServiceInfo(
    name="eufy T9146",
    address="11:22:33:44:55:66",
    rssi=-60,
    manufacturer_data={},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)
