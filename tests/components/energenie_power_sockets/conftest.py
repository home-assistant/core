"""Configure tests for Energenie-Power-Sockets."""

from collections.abc import Generator
from typing import Final
from unittest.mock import MagicMock, patch

from pyegps.fakes.powerstrip import FakePowerStrip
import pytest

from homeassistant.components.energenie_power_sockets.const import (
    CONF_DEVICE_API_ID,
    DOMAIN,
)
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

DEMO_CONFIG_DATA: Final = {
    CONF_NAME: "Unit Test",
    CONF_DEVICE_API_ID: "DYPS:00:11:22",
}


@pytest.fixture
def demo_config_data() -> dict:
    """Return valid user input."""
    return {CONF_DEVICE_API_ID: DEMO_CONFIG_DATA[CONF_DEVICE_API_ID]}


@pytest.fixture
def valid_config_entry() -> MockConfigEntry:
    """Return a valid egps config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_CONFIG_DATA,
        unique_id=DEMO_CONFIG_DATA[CONF_DEVICE_API_ID],
    )


@pytest.fixture(name="pyegps_device_mock")
def get_pyegps_device_mock() -> MagicMock:
    """Fixture for a mocked FakePowerStrip."""

    fkObj = FakePowerStrip(
        devId=DEMO_CONFIG_DATA[CONF_DEVICE_API_ID], number_of_sockets=4
    )
    fkObj.release = lambda: True
    fkObj._status = [0, 1, 0, 1]

    usb_device_mock = MagicMock(wraps=fkObj)
    usb_device_mock.get_device_type.return_value = "PowerStrip"
    usb_device_mock.numberOfSockets = 4
    usb_device_mock.device_id = DEMO_CONFIG_DATA[CONF_DEVICE_API_ID]
    usb_device_mock.manufacturer = "Energenie"
    usb_device_mock.name = "MockedUSBDevice"

    return usb_device_mock


@pytest.fixture(name="mock_get_device")
def patch_get_device(pyegps_device_mock: MagicMock) -> Generator[MagicMock]:
    """Fixture to patch the `get_device` api method."""
    with (
        patch("homeassistant.components.energenie_power_sockets.get_device") as m1,
        patch(
            "homeassistant.components.energenie_power_sockets.config_flow.get_device",
            new=m1,
        ) as mock,
    ):
        mock.return_value = pyegps_device_mock
        yield mock


@pytest.fixture(name="mock_search_for_devices")
def patch_search_devices(
    pyegps_device_mock: MagicMock,
) -> Generator[MagicMock]:
    """Fixture to patch the `search_for_devices` api method."""
    with patch(
        "homeassistant.components.energenie_power_sockets.config_flow.search_for_devices",
        return_value=[pyegps_device_mock],
    ) as mock:
        yield mock
