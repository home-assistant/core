"""Tests for the Chef iQ integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

ADDRESS = "C9:14:65:CA:07:9A"
TITLE = "CQ60 079A"

NOT_CHEFIQ_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="00:00:00:00:00:01",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

# Real CQ60 captures (firmware 5.0.0). The temperature packet (type 0x1) carries
# the food/ambient/tip temperatures; the status packet (type 0x3) carries the
# MAC address, battery percentage and SoC temperature.
CHEFIQ_TEMPERATURE_SERVICE_INFO = BluetoothServiceInfo(
    name="CQ60",
    address="C9:14:65:CA:07:9A",
    rssi=-60,
    manufacturer_data={1485: bytes.fromhex("015024012b0135012e012b0130012401315a")},
    service_data={},
    service_uuids=[],
    source="local",
)

CHEFIQ_STATUS_SERVICE_INFO = BluetoothServiceInfo(
    name="CQ60",
    address="C9:14:65:CA:07:9A",
    rssi=-60,
    manufacturer_data={1485: bytes.fromhex("0350c91465ca079a64201e010301007ac4")},
    service_data={},
    service_uuids=[],
    source="local",
)

# A 0x05CD advertisement that passes the cheap probe pre-filter but is not a
# recognised probe packet (unknown packet type 0x2); must be rejected.
CHEFIQ_UNSUPPORTED_SERVICE_INFO = BluetoothServiceInfo(
    name="CQ60",
    address="C9:14:65:CA:07:9A",
    rssi=-60,
    manufacturer_data={1485: bytes.fromhex("0250")},
    service_data={},
    service_uuids=[],
    source="local",
)

# The iQ Sense base/hub advertises under the same manufacturer id (0x05CD) but
# is not a probe; the config flow must reject it.
IQ_SENSE_SERVICE_INFO = BluetoothServiceInfo(
    name="iQ Sense 540",
    address="94:54:C5:6D:8A:D6",
    rssi=-66,
    manufacturer_data={
        1485: bytes.fromhex("50754e427588e5133f8d4bb3a403113f437a871e05")
    },
    service_data={},
    service_uuids=[],
    source="local",
)
