"""Tests for the SensorPush integration."""

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


NOT_SENSOR_PUSH_SERVICE_INFO = make_bluetooth_service_info(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

HTW_SERVICE_INFO = make_bluetooth_service_info(
    name="SensorPush HT.w 0CA1",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={11271: b"\xfe\x00\x01"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)

HTPWX_SERVICE_INFO = make_bluetooth_service_info(
    name="SensorPush HTP.xw F4D",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={7168: b"\xcd=!\xd1\xb9"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)


HTPWX_EMPTY_SERVICE_INFO = make_bluetooth_service_info(
    name="SensorPush HTP.xw F4D",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)
