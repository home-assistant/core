"""Tests for the melnor integration."""

from __future__ import annotations

from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak

FAKE_ADDRESS_1 = "FAKE-ADDRESS-1"
FAKE_ADDRESS_2 = "FAKE-ADDRESS-2"


FAKE_SERVICE_INFO_1 = BluetoothServiceInfoBleak(
    name="YM_TIMER%",
    address=FAKE_ADDRESS_1,
    rssi=-63,
    manufacturer_data={
        13: b"Y\x08\x02\x8f\x00\x00\x00\x00\x00\x00\xf0\x00\x00\xf0\x00\x00\xf0\x00\x00\xf0*\x9b\xcf\xbc"
    },
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(FAKE_ADDRESS_1, None),
    advertisement=AdvertisementData(local_name=""),
    time=0,
    connectable=True,
)

FAKE_SERVICE_INFO_2 = BluetoothServiceInfoBleak(
    name="YM_TIMER%",
    address=FAKE_ADDRESS_2,
    rssi=-63,
    manufacturer_data={
        13: b"Y\x08\x02\x8f\x00\x00\x00\x00\x00\x00\xf0\x00\x00\xf0\x00\x00\xf0\x00\x00\xf0*\x9b\xcf\xbc"
    },
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(FAKE_ADDRESS_2, None),
    advertisement=AdvertisementData(local_name=""),
    time=0,
    connectable=True,
)


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=return_value,
    )


def patch_async_discovered_service_info(
    return_value: list[BluetoothServiceInfoBleak] = [FAKE_SERVICE_INFO_1],
):
    """Patch async_discovered_service_info a mocked device info."""
    return patch(
        "homeassistant.components.melnor.config_flow.async_discovered_service_info",
        return_value=return_value,
    )
