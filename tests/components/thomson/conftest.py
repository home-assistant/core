"""Fixtures for Thomson integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.thomson.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"
MOCK_USERNAME = "admin"
MOCK_PASSWORD = "password"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}

MOCK_TELNET_OUTPUT = (
    b"aa:bb:cc:dd:ee:ff 192.168.1.100  C     dynamic  nas  eth0  my-phone\r\n"
    b"11:22:33:44:55:66 192.168.1.101  C     dynamic  nas  eth0  my-laptop\r\n"
    b"00:11:22:33:44:55 192.168.1.102  D     dynamic  nas  eth0  old-device\r\n"
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        title=f"Thomson ({MOCK_HOST})",
    )


@pytest.fixture
def mock_telnet() -> Generator[MagicMock]:
    """Mock telnetlib.Telnet."""
    with patch(
        "homeassistant.components.thomson.coordinator.telnetlib.Telnet"
    ) as mock:
        telnet_instance = MagicMock()
        mock.return_value = telnet_instance
        telnet_instance.read_until.side_effect = [
            b"Username : ",
            b"Password : ",
            b"=>",
            MOCK_TELNET_OUTPUT + b"=>",
        ]
        yield mock


@pytest.fixture
def mock_telnet_validate() -> Generator[MagicMock]:
    """Mock telnetlib.Telnet for config flow validation."""
    with patch(
        "homeassistant.components.thomson.coordinator.telnetlib.Telnet"
    ) as mock:
        telnet_instance = MagicMock()
        mock.return_value = telnet_instance
        telnet_instance.read_until.side_effect = [
            b"Username : ",
            b"Password : ",
            b"=>",
        ]
        yield mock


@pytest.fixture
def mock_device_registry_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Create device registry devices so the device tracker entities are enabled."""
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)
    for mac in ("AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"):
        device_registry.async_get_or_create(
            name=f"Device {mac}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        )
