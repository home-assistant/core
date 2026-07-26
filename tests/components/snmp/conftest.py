"""Conftest for SNMP tests."""

import socket
from unittest.mock import Mock, patch

from pysnmp.hlapi.v3arch.asyncio import ObjectType
from pysnmp.proto.rfc1902 import ObjectName, OctetString
import pytest

from homeassistant.components.snmp.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _mock_next_cmd_side_effect(*args: object, **kwargs: object) -> tuple:
    """Return success for next_cmd with a child OID of the queried prefix.

    Extracts the base OID from the ObjectType argument and returns a child
    OID so that the prefix check in validate_input passes.
    """
    if args:
        obj_type = args[-1]
        if isinstance(obj_type, ObjectType):
            base_oid = obj_type._ObjectType__args[0]._ObjectIdentity__args[0]
            child_oid = f"{base_oid}.1"
            return (None, None, None, [[ObjectName(child_oid), OctetString("98F")]])
    return (None, None, None, [[ObjectName("1.1"), OctetString("98F")]])


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
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    )
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


@pytest.fixture(autouse=True)
def mock_next_cmd():
    """Patch next_cmd to return success with a child OID for any base OID."""
    with patch(
        "homeassistant.components.snmp.config_flow.next_cmd",
        side_effect=_mock_next_cmd_side_effect,
    ) as mock:
        yield mock


@pytest.fixture
def mock_setup_entry():
    """Patch async_setup_entry to avoid setting up the integration."""
    with patch(
        "homeassistant.components.snmp.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
