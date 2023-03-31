"""Tests for the melnor integration."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from melnor_bluetooth.device import Device
import pytest

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.melnor.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

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
    device=generate_ble_device(FAKE_ADDRESS_1, None),
    advertisement=generate_advertisement_data(local_name=""),
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
    device=generate_ble_device(FAKE_ADDRESS_2, None),
    advertisement=generate_advertisement_data(local_name=""),
    time=0,
    connectable=True,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


class MockedValve:
    """Mocked class for a Valve."""

    _id: int
    _is_watering: bool
    _manual_watering_minutes: int
    _end_time: int

    def __init__(self, identifier: int) -> None:
        """Initialize a mocked valve."""
        self._end_time = 0
        self._id = identifier
        self._is_watering = False
        self._manual_watering_minutes = 0

    @property
    def id(self) -> int:
        """Return the valve id."""
        return self._id

    @property
    def is_watering(self):
        """Return true if the valve is currently watering."""
        return self._is_watering

    async def set_is_watering(self, is_watering: bool):
        """Set the valve to manual watering."""
        self._is_watering = is_watering

    @property
    def manual_watering_minutes(self):
        """Return the number of minutes the valve is set to manual watering."""
        return self._manual_watering_minutes

    async def set_manual_watering_minutes(self, minutes: int):
        """Set the valve to manual watering."""
        self._manual_watering_minutes = minutes

    @property
    def watering_end_time(self) -> int:
        """Return the end time of the current watering cycle."""
        return self._end_time


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

        device.zone1 = MockedValve(0)
        device.zone2 = MockedValve(1)
        device.zone3 = MockedValve(2)
        device.zone4 = MockedValve(3)

        device.__getitem__.side_effect = lambda key: getattr(device, key)

        return device


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Patch async setup entry to return True."""
    with patch(
        "homeassistant.components.melnor.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


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
