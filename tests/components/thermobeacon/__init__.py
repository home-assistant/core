"""Tests for the ThermoBeacon integration."""

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


NOT_THERMOBEACON_SERVICE_INFO = make_bluetooth_service_info(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

THERMOBEACON_SERVICE_INFO = make_bluetooth_service_info(
    name="ThermoBeacon",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    manufacturer_data={
        16: b"\x00\x00\xb0\x02\x00\x00G\xa4\xe2\x0c\x80\x01\xb6\x02J\x00\x00\x00"
    },
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)
