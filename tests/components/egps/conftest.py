"""Configure tests for egps."""
from collections.abc import Generator
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

from pyegps.fakes.powerstrip import FakePowerStrip
import pytest

from homeassistant.components.egps.const import CONF_DEVICE_API_ID, DOMAIN
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

DEMO_CONFIG_ENTRY: Final = {
    CONF_NAME: "Unit Test",
    CONF_DEVICE_API_ID: "DYPS:00:11:22",
}


@pytest.fixture
def demo_config_data() -> dict:
    """Return valid user input."""
    return {CONF_DEVICE_API_ID: DEMO_CONFIG_ENTRY[CONF_DEVICE_API_ID]}


@pytest.fixture
def valid_config_entry() -> MockConfigEntry:
    """Return a valid egps config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_CONFIG_ENTRY,
        unique_id=DEMO_CONFIG_ENTRY[CONF_DEVICE_API_ID],
    )


@pytest.fixture(name="setup_entry_mock")
def patch_setup_entry() -> Generator[AsyncMock, None, None]:
    """Fixture to patch the `async_setup_entry` method in the egps component."""
    with patch(
        "homeassistant.components.egps.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture(name="pyegps_device_mock")
def patch_pyegps_get_device() -> MagicMock:
    """Fixture for a mocked FakePowerStrip."""

    usb_device_mock = MagicMock(
        wraps=FakePowerStrip(
            devId=DEMO_CONFIG_ENTRY[CONF_DEVICE_API_ID], number_of_sockets=4
        )
    )
    usb_device_mock.get_device_type.return_value = "PowerStrip"
    usb_device_mock.numberOfSockets = 4
    usb_device_mock.device_id = DEMO_CONFIG_ENTRY[CONF_DEVICE_API_ID]
    usb_device_mock.manufacturer = "Energenie"
    usb_device_mock.name = "MockedUSBDevice"

    return usb_device_mock
