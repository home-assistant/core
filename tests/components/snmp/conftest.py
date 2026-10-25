"""Conftest for SNMP tests."""

import binascii
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import Mock, patch

from pysnmp.proto.rfc1902 import OctetString
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from . import mock_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry."""
    entry = mock_entry(baseoid=None)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_walk() -> Iterator[Mock]:
    """Walk the ARP table of 192.168.1.1 and yield a single MAC address."""

    async def side_effect(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        oid = Mock()
        oid.asTuple.return_value = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2, 1, 192, 168, 1, 1)
        yield None, None, None, [(oid, OctetString(binascii.unhexlify("001122334455")))]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=side_effect,
    ) as mock:
        yield mock


@pytest.fixture
def mock_udp_transport() -> Iterator[Mock]:
    """Avoid real network calls when a transport target is created."""
    with patch(
        "homeassistant.components.snmp.util.UdpTransportTarget.create",
        return_value=Mock(),
    ) as mock_create:
        yield mock_create


@pytest.fixture
def mock_setup_entry() -> Iterator[Mock]:
    """Patch async_setup_entry to avoid setting up the integration."""
    with patch(
        "homeassistant.components.snmp.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
