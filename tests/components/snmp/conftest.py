"""Conftest for SNMP tests."""

import socket
from unittest.mock import patch

import pytest

from homeassistant.components.snmp.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def patch_getaddrinfo():
    """Patch getaddrinfo to avoid DNS lookups in SNMP tests."""
    with patch.object(socket, "getaddrinfo"):
        yield


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.1_161_1.3.6.1.4.1.2021.10.1.3.1",
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    )
    entry.add_to_hass(hass)
    return entry
