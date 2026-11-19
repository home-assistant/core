"""Common fixtures for the Keenetic NDMS2 tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from ndms2_client import Device
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.keenetic_ndms2.const import DEFAULT_INTERFACE, DOMAIN
from homeassistant.core import HomeAssistant

from . import CLIENT_MAC, MOCK_DATA, MOCK_ROUTER_INFO


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the Keenetic client."""
    with (
        patch("homeassistant.components.keenetic_ndms2.router.TelnetConnection"),
        patch(
            "homeassistant.components.keenetic_ndms2.router.Client", autospec=True
        ) as mock_client_class,
    ):
        client = mock_client_class.return_value
        client.get_router_info.return_value = MOCK_ROUTER_INFO
        client.get_devices.return_value = [
            Device(
                mac=CLIENT_MAC,
                name="Phone",
                ip="192.168.1.2",
                interface=DEFAULT_INTERFACE,
            )
        ]
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    return entry
