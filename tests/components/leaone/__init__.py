"""Tests for the Leaone integration."""

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


SCALE_SERVICE_INFO = make_bluetooth_service_info(
    name="",
    address="5F:5A:5C:52:D3:94",
    rssi=-63,
    manufacturer_data={57280: b"\x06\xa4\x00\x00\x00\x020_Z\\R\xd3\x94"},
    service_uuids=[],
    service_data={},
    source="local",
)
SCALE_SERVICE_INFO_2 = make_bluetooth_service_info(
    name="",
    address="5F:5A:5C:52:D3:94",
    rssi=-63,
    manufacturer_data={
        57280: b"\x06\xa4\x00\x00\x00\x020_Z\\R\xd3\x94",
        63424: b"\x06\xa4\x13\x80\x00\x021_Z\\R\xd3\x94",
    },
    service_uuids=[],
    service_data={},
    source="local",
)
SCALE_SERVICE_INFO_3 = make_bluetooth_service_info(
    name="",
    address="5F:5A:5C:52:D3:94",
    rssi=-63,
    manufacturer_data={
        57280: b"\x06\xa4\x00\x00\x00\x020_Z\\R\xd3\x94",
        63424: b"\x06\xa4\x13\x80\x00\x021_Z\\R\xd3\x94",
        6592: b"\x06\x8e\x00\x00\x00\x020_Z\\R\xd3\x94",
    },
    service_uuids=[],
    service_data={},
    source="local",
)
