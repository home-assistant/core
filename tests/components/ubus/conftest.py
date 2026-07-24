"""Fixtures for the OpenWrt (ubus) integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ubus.const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_DHCP_SOFTWARE: DEFAULT_DHCP_SOFTWARE,
}

MAC_PHONE = "AA:BB:CC:DD:EE:FF"
MAC_LAPTOP = "11:22:33:44:55:66"
MAC_GUEST = "99:88:77:66:55:44"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ubus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def dhcp_software(request: pytest.FixtureRequest) -> str:
    """Return the DHCP software the mock config entry is created with."""
    return getattr(request, "param", DEFAULT_DHCP_SOFTWARE)


@pytest.fixture
def mock_config_entry(dhcp_software: str) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_DHCP_SOFTWARE: dhcp_software},
        title=MOCK_HOST,
    )


@pytest.fixture
def mock_ubus() -> Generator[MagicMock]:
    """Mock the Ubus client with the raw router API responses."""
    with (
        patch("homeassistant.components.ubus.coordinator.Ubus", autospec=True) as mock,
        patch("homeassistant.components.ubus.config_flow.Ubus", new=mock),
    ):
        instance = mock.return_value
        instance.session_id = None

        def _connect() -> str:
            instance.session_id = "session-id"
            return "session-id"

        instance.connect.side_effect = _connect
        instance.get_hostapd.return_value = {"hostapd.wlan0": {}}
        instance.get_hostapd_clients.return_value = {
            "clients": {
                MAC_PHONE: {"authorized": True},
                MAC_LAPTOP: {"authorized": True},
                MAC_GUEST: {"authorized": False},
            }
        }
        instance.get_uci_config.return_value = {
            "values": {"cfg01": {"leasefile": "/var/dhcp/dnsmasq.leases"}}
        }
        instance.file_read.return_value = {
            "data": (
                "1600000000 aa:bb:cc:dd:ee:ff 192.168.1.10 my-phone *\n"
                "1600000000 11:22:33:44:55:66 192.168.1.11 my-laptop *"
            )
        }
        instance.get_dhcp_method.return_value = {
            "device": {
                "br-lan": {
                    "leases": [
                        {"mac": "aabbccddeeff", "hostname": "my-phone"},
                        {"mac": "112233445566", "hostname": "my-laptop"},
                    ]
                }
            }
        }
        yield mock
