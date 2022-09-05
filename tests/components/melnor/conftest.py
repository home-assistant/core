"""Tests for the melnor integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from melnor_bluetooth.device import Device, Valve

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.melnor.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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


def mock_config_entry(hass: HomeAssistant):
    """Return a mock config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_ADDRESS_1,
        data={CONF_ADDRESS: FAKE_ADDRESS_1},
    )
    entry.add_to_hass(hass)

    return entry


def mock_melnor_device():
    """Return a mocked Melnor device."""

    with patch("melnor_bluetooth.device.Device") as mock:

        device = mock.return_value

        device.connect = AsyncMock(return_value=True)
        device.disconnect = AsyncMock(return_value=True)
        device.fetch_state = AsyncMock(return_value=device)
        device.push_state = AsyncMock(return_value=None)

        device.battery_level = 80
        device.mac = FAKE_ADDRESS_1
        device.model = "test_model"
        device.name = "test_melnor"
        device.rssi = -50

        device.zone1 = Valve(0, device)
        device.zone2 = Valve(1, device)
        device.zone3 = Valve(2, device)
        device.zone4 = Valve(3, device)

        device.__getitem__.side_effect = lambda key: getattr(device, key)

        return device


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=return_value,
    )


# pylint: disable=dangerous-default-value
def patch_async_discovered_service_info(
    return_value: list[BluetoothServiceInfoBleak] = [FAKE_SERVICE_INFO_1],
):
    """Patch async_discovered_service_info a mocked device info."""
    return patch(
        "homeassistant.components.melnor.config_flow.async_discovered_service_info",
        return_value=return_value,
    )


def patch_async_ble_device_from_address(
    return_value: BluetoothServiceInfoBleak | None = FAKE_SERVICE_INFO_1,
):
    """Patch async_ble_device_from_address to return a mocked BluetoothServiceInfoBleak."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


def patch_melnor_device(device: Device = mock_melnor_device()):
    """Patch melnor_bluetooth.device to return a mocked Melnor device."""
    return patch("homeassistant.components.melnor.Device", return_value=device)


def patch_async_register_callback():
    """Patch async_register_callback to return True."""
    return patch("homeassistant.components.bluetooth.async_register_callback")
