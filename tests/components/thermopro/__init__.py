"""Tests for the ThermoPro integration."""

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


NOT_THERMOPRO_SERVICE_INFO = make_bluetooth_service_info(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)


TP357_SERVICE_INFO = make_bluetooth_service_info(
    name="TP357 (2142)",
    manufacturer_data={61890: b"\x00\x1d\x02,"},
    service_uuids=[],
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-60,
    service_data={},
    source="local",
)

TP358_SERVICE_INFO = make_bluetooth_service_info(
    name="TP358 (4221)",
    manufacturer_data={61890: b"\x00\x1d\x02,"},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-65,
    service_data={},
    source="local",
)

TP962R_SERVICE_INFO = make_bluetooth_service_info(
    name="TP962R (0000)",
    manufacturer_data={14081: b"\x00;\x0b7\x00"},
    service_uuids=["72fbb631-6f6b-d1ba-db55-2ee6fdd942bd"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-52,
    service_data={},
    source="local",
)

TP962R_SERVICE_INFO_2 = make_bluetooth_service_info(
    name="TP962R (0000)",
    manufacturer_data={17152: b"\x00\x17\nC\x00", 14081: b"\x00;\x0b7\x00"},
    service_uuids=["72fbb631-6f6b-d1ba-db55-2ee6fdd942bd"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-52,
    service_data={},
    source="local",
)
