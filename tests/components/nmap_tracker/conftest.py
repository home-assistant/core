"""Fixtures for the Nmap Tracker integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.nmap_tracker.const import (
    CONF_HOME_INTERVAL,
    CONF_HOSTS_EXCLUDE,
    CONF_HOSTS_LIST,
    CONF_MAC_EXCLUDE,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import scan_result


@pytest.fixture
def mock_port_scanner() -> Generator[MagicMock]:
    """Mock the nmap port scanner."""
    with (
        patch("homeassistant.components.nmap_tracker.PortScanner") as mock_scanner,
        patch(
            "homeassistant.components.nmap_tracker.aiooui.is_loaded",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nmap_tracker.aiooui.get_vendor",
            return_value="Vendor",
        ),
    ):
        scanner = mock_scanner.return_value
        scanner.scan.return_value = scan_result("phone.lan")
        yield scanner


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_HOSTS_LIST: ["192.168.1.0/24"],
            CONF_HOSTS_EXCLUDE: [],
            CONF_MAC_EXCLUDE: [],
            CONF_HOME_INTERVAL: 0,
            CONF_OPTIONS: DEFAULT_OPTIONS,
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry
