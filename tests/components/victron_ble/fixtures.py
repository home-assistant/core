"""Fixtures for testing victron_ble."""

from home_assistant_bluetooth import BluetoothServiceInfo

NOT_VICTRON_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_TEST_WRONG_TOKEN = "00000000000000000000000000000000"

# battery monitor
VICTRON_BATTERY_MONITOR_SERVICE_INFO = BluetoothServiceInfo(
    name="Battery Monitor",
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
VICTRON_BATTERY_MONITOR_SENSORS = {
    "battery_monitor_aux_mode": "disabled",
    "battery_monitor_consumed_ampere_hours": "-50.0",
    "battery_monitor_current": "0.0",
    "battery_monitor_remaining_minutes": "unknown",
    "battery_monitor_state_of_charge": "50.0",
    "battery_monitor_voltage": "12.53",
    "battery_monitor_alarm": "none",
    "battery_monitor_temperature": "unknown",
    "battery_monitor_starter_voltage": "unknown",
    "battery_monitor_midpoint_voltage": "unknown",
}

# DC/DC converter

VICTRON_DC_DC_CONVERTER_SERVICE_INFO = BluetoothServiceInfo(
    name="DC/DC Converter",
    address="01:02:03:04:05:08",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("1000c0a304121d64ca8d442b90bbdf6a8cba"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)

# DC energy meter

VICTRON_DC_ENERGY_METER_SERVICE_INFO = BluetoothServiceInfo(
    name="DC Energy Meter",
    address="01:02:03:04:05:09",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100289a30d787fafde83ccec982199fd815286"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_DC_ENERGY_METER_TOKEN = "aff4d0995b7d1e176c0c33ecb9e70dcd"

VICTRON_DC_ENERGY_METER_SENSORS = {
    "dc_energy_meter_meter_type": "dc_dc_charger",
    "dc_energy_meter_aux_mode": "starter_voltage",
    "dc_energy_meter_current": "0.0",
    "dc_energy_meter_voltage": "12.52",
    "dc_energy_meter_starter_voltage": "-0.01",
    "dc_energy_meter_alarm": "none",
    "dc_energy_meter_temperature": "unknown",
}

# Inverter

VICTRON_INVERTER_SERVICE_INFO = BluetoothServiceInfo(
    name="Inverter",
    address="01:02:03:04:05:10",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("1003a2a2031252dad26f0b8eb39162074d140df410"),
    },  # not a valid advertisement, but model id mangled to match inverter
    service_data={},
    service_uuids=[],
    source="local",
)

# Solar charger

VICTRON_SOLAR_CHARGER_SERVICE_INFO = BluetoothServiceInfo(
    name="Solar Charger",
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

VICTRON_SOLAR_CHARGER_SENSORS = {
    "solar_charger_charge_state": "absorption",
    "solar_charger_battery_voltage": "13.88",
    "solar_charger_battery_current": "1.4",
    "solar_charger_yield_today": "30",
    "solar_charger_solar_power": "19",
    "solar_charger_external_device_load": "0.0",
}

# ve.bus

VICTRON_VEBUS_SERVICE_INFO = BluetoothServiceInfo(
    name="Inverter Charger",
    address="01:02:03:04:05:06",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100380270c1252dad26f0b8eb39162074d140df410")
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_VEBUS_TOKEN = "da3f5fa2860cb1cf86ba7a6d1d16b9dd"

VICTRON_VEBUS_SENSORS = {
    "inverter_charger_device_state": "float",
    "inverter_charger_battery_voltage": "14.45",
    "inverter_charger_battery_current": "23.2",
    "inverter_charger_ac_in_state": "AC_IN_1",
    "inverter_charger_ac_in_power": "1459",
    "inverter_charger_ac_out_power": "1046",
    "inverter_charger_battery_temperature": "32",
    "inverter_charger_state_of_charge": "unknown",
}
