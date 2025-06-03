"""Tests for the SensorPro integration."""

from uuid import UUID

from bleak.backends.device import BLEDevice
from bluetooth_data_tools import monotonic_time_coarse

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak


def make_bluetooth_service_info(
    name: str,
    manufacturer_data: dict[int, bytes],
    service_uuids: list[str],
    address: str,
    rssi: int,
    service_data: dict[UUID, bytes],
    source: str,
    tx_power: int = 0,
    raw: bytes | None = None,
) -> BluetoothServiceInfoBleak:
    """Create a BluetoothServiceInfoBleak object for testing."""
    return BluetoothServiceInfoBleak(
        name=name,
        manufacturer_data=manufacturer_data,
        service_uuids=service_uuids,
        address=address,
        rssi=rssi,
        service_data=service_data,
        source=source,
        device=BLEDevice(
            name=name,
            address=address,
            details={},
            rssi=rssi,
        ),
        time=monotonic_time_coarse(),
        advertisement=None,
        connectable=True,
        tx_power=tx_power,
        raw=raw,
    )


NOT_SENSORPRO_SERVICE_INFO = make_bluetooth_service_info(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

SENSORPRO_SERVICE_INFO = make_bluetooth_service_info(
    name="T201",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    manufacturer_data={
        43605: b"\x01\x01\xa4\xc18.\xcan\x01\x07\n\x02\x13\x9dd\x00\x01\x01\x01\xa4\xc18.\xcan\x01\x07\n\x02\x13\x9dd\x00\x01"
    },
    service_uuids=[],
    source="local",
)
