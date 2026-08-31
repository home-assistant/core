"""Tests for the Qingping integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_QINGPING_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

LIGHT_AND_SIGNAL_SERVICE_INFO = BluetoothServiceInfo(
    name="Qingping Motion & Light",
    manufacturer_data={},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={
        "0000fdcd-0000-1000-8000-00805f9b34fb": (
            b"H\x12\xcd\xd5`4-X\x08\x04\x00\r\x00\x00\x0f\x01\xee"
        )
    },
    source="local",
)

# Non-event variant (first byte 0x08 instead of 0x48 clears the event bit);
# qingping-ble 1.1.3 drops illuminance from CGPR1 event packets because the
# trailing bytes after motion are not a valid reading there.
LIGHT_SERVICE_INFO = BluetoothServiceInfo(
    name="Qingping Motion & Light",
    manufacturer_data={},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={
        "0000fdcd-0000-1000-8000-00805f9b34fb": (
            b"\x08\x12\xcd\xd5`4-X\x08\x04\x00\r\x00\x00\x0f\x01\xee"
        )
    },
    source="local",
)


NO_DATA_SERVICE_INFO = BluetoothServiceInfo(
    name="Qingping Motion & Light",
    manufacturer_data={},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={
        "0000fdcd-0000-1000-8000-00805f9b34fb": b"0X\x83\n\x02\xcd\xd5`4-X\x08"
    },
    source="local",
)


# A captured payload from a device publishing on qingping/<mac>/up; the
# last frame of the history decodes to temperature 25.8 and humidity 65.3.
MQTT_MAC = "582D3412A4C2"
MQTT_TLV_PAYLOAD = bytes.fromhex(
    "4347422e013802003a00650100c9640100ff7402000000110500312e332e3685"
    "1f00a0678d6a13f700d90297010000000000000000340033002b020000e70110"
    "02851f00246b8d6a13f700d5029201000000000000000034003200ec010000a1"
    "011006851f00a86e8d6a13f700d5029001010001000100010034003500cc0100"
    "00f7001006851f002c728d6a13f200db029301010001000100010052003b009d"
    "01000090001006851f004c6f8e6a13fc00ae0291010000000000000000340033"
    "00f3040000ea011002851f00d0728e6a13000196029101000000000000000035"
    "00300070030000e3011006851f0054768e6a1302018d02980100000000000000"
    "0040003200ca030000bc011006851f00d8798e6a1302018d02bf010000000000"
    "0000004a003100000400002c0110061d010000a138"
)
