"""Conftest for SNMP tests."""

import socket
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import HomeAssistant

from . import mock_entry

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def patch_getaddrinfo():
    """Patch getaddrinfo to avoid DNS lookups in SNMP tests."""
    with patch.object(socket, "getaddrinfo"):
        yield


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(autouse=True)
def mock_udp_transport():
    """Patch UdpTransportTarget.create to avoid real network calls."""
    with patch(
        "homeassistant.components.snmp.util.UdpTransportTarget.create",
        return_value=Mock(),
    ) as mock_create:
        yield mock_create


@pytest.fixture
def mock_setup_entry():
    """Patch async_setup_entry to avoid setting up the integration."""
    with patch(
        "homeassistant.components.snmp.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
