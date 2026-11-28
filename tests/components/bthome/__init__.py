"""Tests for the BTHome integration."""

import time
from typing import Any

from habluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    DiscoveredDeviceAdvertisementData,
    discovered_device_advertisement_data_to_dict,
)
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
)

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, storage

BTHOME_UUID = "0000fcd2-0000-1000-8000-00805f9b34fb"

TEMP_HUMI_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="ATC 8D18B2",
    address="A4:C1:38:8D:18:B2",
    device=generate_ble_device("A4:C1:38:8D:18:B2", None),
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000181c-0000-1000-8000-00805f9b34fb": b"#\x02\xca\t\x03\x03\xbf\x13"
    },
    service_uuids=["0000181c-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

TEMP_HUMI_ENCRYPTED_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="TEST DEVICE 8F80A5",
    address="54:48:E6:8F:80:A5",
    device=generate_ble_device("54:48:E6:8F:80:A5", None),
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000181e-0000-1000-8000-00805f9b34fb": (
            b'\xfb\xa45\xe4\xd3\xc3\x12\xfb\x00\x11"3W\xd9\n\x99'
        )
    },
    service_uuids=["0000181e-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

PRST_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="prst 8F80A5",
    address="54:48:E6:8F:80:A5",
    device=generate_ble_device("54:48:E6:8F:80:A5", None),
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000181c-0000-1000-8000-00805f9b34fb": (
            b'\x02\x14\x00\n"\x02\xdd\n\x02\x03{\x12\x02\x0c\n\x0b'
        )
    },
    service_uuids=["0000181c-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="prst"),
    time=0,
    connectable=False,
    tx_power=-127,
)

INVALID_PAYLOAD = BluetoothServiceInfoBleak(
    name="ATC 565384",
    address="A4:C1:38:56:53:84",
    device=generate_ble_device("A4:C1:38:56:53:84", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000181c-0000-1000-8000-00805f9b34fb": b"0X[\x05\x02\x84\x53\x568\xc1\xa4\x08",
    },
    service_uuids=["0000181c-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

NOT_BTHOME_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Not it",
    address="00:00:00:00:00:00",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)


def make_bthome_v1_adv(address: str, payload: bytes) -> BluetoothServiceInfoBleak:
    """Make a dummy advertisement."""
    return BluetoothServiceInfoBleak(
        name="Test Device",
        address=address,
        device=generate_ble_device(address, None),
        rssi=-56,
        manufacturer_data={},
        service_data={
            "0000181c-0000-1000-8000-00805f9b34fb": payload,
        },
        service_uuids=["0000181c-0000-1000-8000-00805f9b34fb"],
        source="local",
        advertisement=generate_advertisement_data(local_name="Test Device"),
        time=0,
        connectable=False,
        tx_power=-127,
    )


def make_encrypted_bthome_v1_adv(
    address: str, payload: bytes
) -> BluetoothServiceInfoBleak:
    """Make a dummy encrypted advertisement."""
    return BluetoothServiceInfoBleak(
        name="ATC 8F80A5",
        address=address,
        device=generate_ble_device(address, None),
        rssi=-56,
        manufacturer_data={},
        service_data={
            "0000181e-0000-1000-8000-00805f9b34fb": payload,
        },
        service_uuids=["0000181e-0000-1000-8000-00805f9b34fb"],
        source="local",
        advertisement=generate_advertisement_data(local_name="ATC 8F80A5"),
        time=0,
        connectable=False,
        tx_power=-127,
    )


def make_bthome_v2_adv(address: str, payload: bytes) -> BluetoothServiceInfoBleak:
    """Make a dummy advertisement."""
    return BluetoothServiceInfoBleak(
        name="Test Device",
        address=address,
        device=generate_ble_device(address, None),
        rssi=-56,
        manufacturer_data={},
        service_data={
            "0000fcd2-0000-1000-8000-00805f9b34fb": payload,
        },
        service_uuids=["0000fcd2-0000-1000-8000-00805f9b34fb"],
        source="local",
        advertisement=generate_advertisement_data(local_name="Test Device"),
        time=0,
        connectable=False,
        tx_power=-127,
    )


def _stored_packets(
    packets: dict[str, tuple[bytes, int, float]], now: float
) -> dict[str, Any]:
    """Return stored advertisements as Bluetooth storage data."""
    return discovered_device_advertisement_data_to_dict(
        DiscoveredDeviceAdvertisementData(
            connectable=False,
            expire_seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
            discovered_device_advertisement_datas={
                address: (
                    generate_ble_device(address, "Test Device"),
                    generate_advertisement_data(
                        local_name="Test Device",
                        service_data={BTHOME_UUID: payload},
                        service_uuids=[BTHOME_UUID],
                        rssi=rssi,
                    ),
                )
                for address, (payload, rssi, _) in packets.items()
            },
            discovered_device_timestamps={
                address: now - age for address, (_, _, age) in packets.items()
            },
        )
    )


def make_bluetooth_storage(
    proxies: dict[str, dict[str, tuple[bytes, int, float]]],
    accepted: dict[str, tuple[str, tuple[bytes, int, float]]],
) -> dict[str, Any]:
    """Return Bluetooth storage with packets per proxy and the accepted ones.

    Each packet is (payload, rssi, age in seconds); accepted packets are keyed by
    address with the proxy they came from.
    """
    now = time.monotonic()
    return {
        storage.REMOTE_SCANNER_STORAGE_KEY: {
            "version": storage.REMOTE_SCANNER_STORAGE_VERSION,
            "minor_version": 1,
            "key": storage.REMOTE_SCANNER_STORAGE_KEY,
            "data": {
                proxy: _stored_packets(packets, now)
                for proxy, packets in proxies.items()
            },
        },
        storage.EVENT_DRIVEN_STORAGE_KEY: {
            "version": storage.EVENT_DRIVEN_STORAGE_VERSION,
            "minor_version": 1,
            "key": storage.EVENT_DRIVEN_STORAGE_KEY,
            "data": {
                "sources": {
                    address: {"source": source, "connectable": False}
                    for address, (source, _) in accepted.items()
                },
                "advertisements": _stored_packets(
                    {address: packet for address, (_, packet) in accepted.items()},
                    now,
                ),
            },
        },
    }
