"""Fixtures for the OpenWrt (ubus) integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ubus.config_flow import HUB_TITLE
from homeassistant.components.ubus.const import (
    CONF_DHCP_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DOMAIN,
    SUBENTRY_TYPE_ROUTER,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MOCK_HOST = "192.168.1.1"
MOCK_HOST_B = "192.168.1.2"
MOCK_HOST_C = "192.168.1.3"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_DHCP_SOFTWARE: DEFAULT_DHCP_SOFTWARE,
}

MOCK_HOST_CONFIG_B = {**MOCK_CONFIG, CONF_HOST: MOCK_HOST_B}
MOCK_HOST_CONFIG_C = {**MOCK_CONFIG, CONF_HOST: MOCK_HOST_C}

MAC_PHONE = "aa:bb:cc:dd:ee:ff"
MAC_LAPTOP = "11:22:33:44:55:66"
MAC_GUEST = "99:88:77:66:55:44"


def router_subentry_data(config: dict[str, Any]) -> dict[str, Any]:
    """Return the subentry data for a router configuration."""
    return {
        "data": dict(config),
        "subentry_type": SUBENTRY_TYPE_ROUTER,
        "title": config[CONF_HOST],
        "unique_id": config[CONF_HOST],
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ubus.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def dhcp_software() -> str:
    """Return the DHCP software the router subentry is created with."""
    return DEFAULT_DHCP_SOFTWARE


@pytest.fixture
def hub_entry(dhcp_software: str) -> MockConfigEntry:
    """Return a mock hub entry with a single router subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[
            router_subentry_data({**MOCK_CONFIG, CONF_DHCP_SOFTWARE: dhcp_software})
        ],
    )


@pytest.fixture
def two_router_hub() -> MockConfigEntry:
    """Return a mock hub entry with two router subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        title=HUB_TITLE,
        subentries_data=[
            router_subentry_data(MOCK_CONFIG),
            router_subentry_data(MOCK_HOST_CONFIG_B),
        ],
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
        # Pre-create the known hosts so tests can configure the clients
        # before the entry is set up.
        _create(f"http://{MOCK_HOST}/ubus", "root", "password", verify=True)
        _create(f"http://{MOCK_HOST_B}/ubus", "root", "password", verify=True)
        yield mock, instances
