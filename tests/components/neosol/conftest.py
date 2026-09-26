"""Test fixtures for the Profalux Neosol integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from pyneosol import Channel, Dongle, DongleInfo
import pytest

from homeassistant.components import usb
from homeassistant.components.neosol.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_PORT, MOCK_SERIAL

from tests.common import MockConfigEntry

CHANNELS = [
    Channel(index=0, serial="000AAAA1", sync=43, key="0123456789ABCDEF"),
    Channel(index=1, serial="000AAAA2", sync=14, key="FEDCBA9876543210"),
]


@pytest.fixture(autouse=True)
def mock_usb_component(hass: HomeAssistant) -> None:
    """Pretend the USB component is set up, as the manifest depends on it."""
    hass.config.components.add("usb")


@pytest.fixture(autouse=True)
def mock_get_serial_by_id() -> Generator[MagicMock]:
    """Return the port unchanged: /dev/serial/by-id does not exist in tests."""
    with patch.object(
        usb, "get_serial_by_id", side_effect=lambda path: path
    ) as mock_get_serial_by_id:
        yield mock_get_serial_by_id


@pytest.fixture
def mock_dongle_class() -> Generator[MagicMock]:
    """Patch the pyneosol Dongle class the integration opens."""
    with patch(
        "homeassistant.components.neosol.coordinator.Dongle", autospec=True
    ) as dongle_class:
        # autospec on the class does not spec what open() returns, and every method of a
        # Dongle is now a coroutine, so the instance is specced explicitly.
        dongle = create_autospec(Dongle, instance=True)
        dongle_class.open.return_value = dongle
        dongle.info.return_value = DongleInfo(
            hardware_version="0",
            software_version="Rev10",
            serial_number=MOCK_SERIAL,
            frame_repeat="T0=25,T1=15,T2=70,T3=70",
            return_code_active=True,
            read_protection=False,
        )
        dongle.used_channels.return_value = list(CHANNELS)
        yield dongle_class


@pytest.fixture
def mock_dongle(mock_dongle_class: MagicMock) -> MagicMock:
    """Return the dongle instance the integration gets from the class."""
    return mock_dongle_class.open.return_value


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out the entry setup, for config flow tests."""
    with patch(
        "homeassistant.components.neosol.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the dongle."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Profalux Neosol",
        data={CONF_DEVICE: MOCK_PORT},
        unique_id=MOCK_SERIAL,
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )
