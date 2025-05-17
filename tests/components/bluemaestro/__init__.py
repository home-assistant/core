"""Tests for the BlueMaestro integration."""

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


NOT_BLUEMAESTRO_SERVICE_INFO = make_bluetooth_service_info(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

BLUEMAESTRO_SERVICE_INFO = make_bluetooth_service_info(
    name="FA17B62C",
    manufacturer_data={
        307: b"\x17d\x0e\x10\x00\x02\x00\xf2\x01\xf2\x00\x83\x01\x00\x01\r\x02\xab\x00\xf2\x01\xf2\x01\r\x02\xab\x00\xf2\x01\xf2\x00\xff\x02N\x00\x00\x00\x00\x00"
    },
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    service_uuids=[],
    source="local",
)
