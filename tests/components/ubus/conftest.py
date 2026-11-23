"""Fixtures for the OpenWrt (ubus) integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ubus.const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

MOCK_HOST = "192.168.1.1"
MOCK_HOST_B = "192.168.1.2"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_DHCP_SOFTWARE: DEFAULT_DHCP_SOFTWARE,
}

MAC_PHONE = "AA:BB:CC:DD:EE:FF"
MAC_LAPTOP = "11:22:33:44:55:66"
MAC_GUEST = "99:88:77:66:55:44"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ubus.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def dhcp_software() -> str:
    """Return the DHCP software the mock config entry is created with."""
    return DEFAULT_DHCP_SOFTWARE


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


@pytest.fixture
async def two_router_entries(
    hass: HomeAssistant,
    mock_ubus_by_host: tuple[MagicMock, dict[str, MagicMock]],
) -> tuple[MockConfigEntry, MockConfigEntry]:
    """Return two ubus config entries, set up one per mock router."""
    _mock, _instances = mock_ubus_by_host
    entry_a = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B},
        title=MOCK_HOST_B,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()
    return entry_a, entry_b


@pytest.fixture
def mock_ubus_by_host() -> Generator[tuple[MagicMock, dict[str, MagicMock]]]:
    """Mock the Ubus client with a separate client instance per router host."""
    instances: dict[str, MagicMock] = {}

    def _create(
        url: str, username: str, password: str, verify: bool = True
    ) -> MagicMock:
        host = (
            url.removeprefix("https://").removeprefix("http://").removesuffix("/ubus")
        )
        if host not in instances:
            instance = MagicMock()
            instance.session_id = None

            def _connect() -> str:
                instance.session_id = "session-id"
                return "session-id"

            instance.connect.side_effect = _connect
            instance.get_hostapd.return_value = {"hostapd.wlan0": {}}
            instance.get_hostapd_clients.return_value = {"clients": {}}
            instance.get_uci_config.return_value = {
                "values": {"cfg01": {"leasefile": "/var/dhcp/dnsmasq.leases"}}
            }
            instance.file_read.return_value = {"data": ""}
            instances[host] = instance
        return instances[host]

    with (
        patch(
            "homeassistant.components.ubus.coordinator.Ubus", side_effect=_create
        ) as mock,
        patch("homeassistant.components.ubus.config_flow.Ubus", side_effect=_create),
    ):
        yield mock, instances
