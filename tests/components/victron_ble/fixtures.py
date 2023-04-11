"""Fixtures for testing victron_ble."""
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_VICTRON_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_VEBUS_SERVICE_INFO = BluetoothServiceInfo(
    name="Inverter/charger",
    address="01:02:03:04:05:06",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100380270c1252dad26f0b8eb39162074d140df410")
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_VEBUS_TOKEN = "DA3F5FA2860CB1CF86BA7A6D1D16B9DD"

VICTRON_TEST_WRONG_TOKEN = "00000000000000000000000000000000"

VICTRON_BATTERY_MONITOR_SERVICE_INFO = BluetoothServiceInfo(
    name="Battery monitor",
    address="01:02:03:04:05:07",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100289a302b040af925d09a4d89aa0128bdef48c6298a9")
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_BATTERY_MONITOR_TOKEN = "aff4d0995b7d1e176c0c33ecb9e70dcd"

VICTRON_BATTERY_SENSE_SERVICE_INFO = BluetoothServiceInfo(
    name="Battery sense",
    address="01:02:03:04:05:08",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("1000a4a3025f150d8dcbff517f30eb65e76b22a04ac4e1"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_BATTERY_SENSE_TOKEN = "0da694539597f9cf6c613cde60d7bf05"

VICTRON_DC_ENERGY_METER_SERVICE_INFO = BluetoothServiceInfo(
    name="DC energy meter",
    address="01:02:03:04:05:09",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100289a30d787fafde83ccec982199fd815286"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_DC_ENERGY_METER_TOKEN = "100289a30d787fafde83ccec982199fd815286"

VICTRON_DC_DC_CONVERTER_SERVICE_INFO = BluetoothServiceInfo(
    name="DC/DC converter",
    address="01:02:03:04:05:10",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("1000c0a304121d64ca8d442b90bbdf6a8cba"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_SOLAR_CHARGER_SERVICE_INFO = BluetoothServiceInfo(
    name="Solar charger",
    address="01:02:03:04:05:11",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100242a0016207adceb37b605d7e0ee21b24df5c"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_SOLAR_CHARGER_TOKEN = "adeccb947395801a4dd45a2eaa44bf17"
