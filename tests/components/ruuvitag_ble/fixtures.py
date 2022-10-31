"""Fixtures for testing RuuviTag BLE."""
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

RUUVITAG_SERVICE_INFO = BluetoothServiceInfo(
    name="RuuviTag 0911",
    address="01:03:05:07:09:11",  # Ignored (the payload encodes the correct MAC)
    rssi=-60,
    manufacturer_data={
        1177: b"\x05\x05\xa0`\xa0\xc8\x9a\xfd4\x02\x8c\xff\x00cvriv\xde\xad{?\xef\xaf"
    },
    service_data={},
    service_uuids=[],
    source="local",
)
CONFIGURED_NAME = "RuuviTag EFAF"
CONFIGURED_PREFIX = CONFIGURED_NAME.lower().replace(":", "_").replace(" ", "_")
