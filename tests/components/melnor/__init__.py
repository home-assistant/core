"""Tests for the melnor integration."""

from __future__ import annotations

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

FAKE_ADDRESS = "FDBC1347-8D0B-DB0E-8D79-7341E825AC2A"

FAKE_SERVICE_INFO = BluetoothServiceInfo(
    name="YM_TIMER%",
    address=FAKE_ADDRESS,
    rssi=-63,
    manufacturer_data={
        13: b"Y\x08\x02\x8f\x00\x00\x00\x00\x00\x00\xf0\x00\x00\xf0\x00\x00\xf0\x00\x00\xf0*\x9b\xcf\xbc"
    },
    service_uuids=[],
    service_data={},
    source="local",
)
