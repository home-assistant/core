"""Tests for the SNMP client."""

import binascii
from collections.abc import AsyncIterator
import inspect
from typing import Any
from unittest.mock import Mock, patch

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    bulk_walk_cmd,
    walk_cmd,
)
from pysnmp.proto.rfc1902 import OctetString
import pytest

from homeassistant.components.snmp.client import SnmpClient

BASE_OID = "1.3.6.1.2.1.4.22.1.2"


def _client(version: str) -> SnmpClient:
    """Return a client for a device of the given SNMP version."""
    return SnmpClient(
        engine=Mock(),
        auth_data=CommunityData("public"),
        target=Mock(),
        context_data=ContextData(),
        version=version,
    )


async def _walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
    """Yield a single row of the ARP table."""
    oid = Mock()
    oid.asTuple.return_value = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2, 1, 192, 168, 1, 1)
    yield None, None, None, [(oid, OctetString(binascii.unhexlify("001122334455")))]


def test_walk_commands_are_generators() -> None:
    """Test that the commands of async_walk yield rows instead of one response."""
    assert inspect.isasyncgenfunction(walk_cmd)
    assert inspect.isasyncgenfunction(bulk_walk_cmd)


@pytest.mark.parametrize("version", ["2c", "3"])
async def test_walk_uses_getbulk(version: str) -> None:
    """Test that the versions which have GETBULK walk with it."""
    client = _client(version)
    bulk_walk = Mock(side_effect=_walk)
    next_walk = Mock(side_effect=_walk)

    with (
        patch("homeassistant.components.snmp.client.bulk_walk_cmd", bulk_walk),
        patch("homeassistant.components.snmp.client.walk_cmd", next_walk),
    ):
        varbinds = [varbind async for varbind in client.async_walk(BASE_OID)]

    assert len(varbinds) == 1
    assert bulk_walk.called
    assert not next_walk.called


async def test_walk_uses_getnext_for_v1() -> None:
    """Test that SNMPv1, which has no GETBULK, walks with GETNEXT instead."""
    client = _client("1")
    bulk_walk = Mock(side_effect=_walk)
    next_walk = Mock(side_effect=_walk)

    with (
        patch("homeassistant.components.snmp.client.bulk_walk_cmd", bulk_walk),
        patch("homeassistant.components.snmp.client.walk_cmd", next_walk),
    ):
        varbinds = [varbind async for varbind in client.async_walk(BASE_OID)]

    assert len(varbinds) == 1
    assert next_walk.called
    assert not bulk_walk.called
