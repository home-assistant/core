"""Tests for the INKBIRD integration."""

from uuid import UUID

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import MONOTONIC_TIME, BluetoothServiceInfoBleak


def _make_bluetooth_service_info(
    name: str,
    manufacturer_data: dict[int, bytes],
    service_uuids: list[str],
    address: str,
    rssi: int,
    service_data: dict[UUID, bytes],
    source: str,
    tx_power: int = 0,
) -> BluetoothServiceInfoBleak:
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
        time=MONOTONIC_TIME(),
        advertisement=None,
        connectable=True,
        tx_power=tx_power,
    )


NOT_INKBIRD_SERVICE_INFO = _make_bluetooth_service_info(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

SPS_SERVICE_INFO = _make_bluetooth_service_info(
    name="sps",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    service_data={},
    manufacturer_data={2096: b"\x0f\x12\x00Z\xc7W\x06"},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)


SPS_PASSIVE_SERVICE_INFO = _make_bluetooth_service_info(
    name="sps",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-63,
    service_data={},
    manufacturer_data={},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)


SPS_WITH_CORRUPT_NAME_SERVICE_INFO = _make_bluetooth_service_info(
    name="XXXXcorruptXXXX",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-63,
    service_data={},
    manufacturer_data={2096: b"\x0f\x12\x00Z\xc7W\x06"},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)


IBBQ_SERVICE_INFO = _make_bluetooth_service_info(
    name="iBBQ",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={
        0: b"\x00\x000\xe2\x83}\xb5\x02\xc8\x00\xc8\x00\xc8\x00\xc8\x00"
    },
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)


IAM_T1_SERVICE_INFO = _make_bluetooth_service_info(
    name="Ink@IAM-T1",
    manufacturer_data={12628: b"AC-6200a13cae\x00\x00"},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    address="62:00:A1:3C:AE:7B",
    rssi=-44,
    service_data={},
    source="local",
)
