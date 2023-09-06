"""Test the thread websocket API."""

import dataclasses
import time
from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from zeroconf import DNSCache, ServiceInfo

from homeassistant.components.thread import dataset_store
from homeassistant.components.thread.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import DATASET_1

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

TEST_ZEROCONF_RECORD_1 = ServiceInfo(
    type_="_meshcop._udp.local.",
    name="HomeAssistant OpenThreadBorderRouter #0BBF._meshcop._udp.local.",
    addresses=["127.0.0.1", "fe80::10ed:6406:4ee9:85e5"],
    port=8080,
    properties={
        "rv": "1",
        "vn": "HomeAssistant",
        "mn": "OpenThreadBorderRouter",
        "nn": "OpenThread HC",
        "xp": "\xe6\x0f\xc7\xc1\x86!,\xe5",
        "tv": "1.3.0",
        "xa": "\xae\xeb/YKW\x0b\xbf",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
)

TEST_ZEROCONF_RECORD_2 = ServiceInfo(
    type_="_meshcop._udp.local.",
    name="HomePod._meshcop._udp.local.",
    addresses=["127.0.0.1", "fe80::10ed:6406:4ee9:85e4"],
    port=8080,
    properties={
        "rv": "1",
        "vn": "Apple",
        "nn": "OpenThread HC",
        "xp": "\xe6\x0f\xc7\xc1\x86!,\xe5",
        "tv": "1.2.0",
        "xa": "\xae\xeb/YKW\x0b\xbf",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
)


TEST_ZEROCONF_RECORD_3 = ServiceInfo(
    type_="_meshcop._udp.local.",
    name="office._meshcop._udp.local.",
    addresses=["127.0.0.1", "fe80::10ed:6406:4ee9:85e0"],
    port=8080,
    properties={
        "rv": "1",
        "vn": "Apple",
        "nn": "OpenThread HC",
        "xp": "\xe6\x0f\xc7\xc1\x86!,\xe5",
        "tv": "1.2.0",
        "xa": "\xae\xeb/YKW\x0b\xbf",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
)

TEST_ZEROCONF_RECORD_4 = ServiceInfo(
    type_="_meshcop._udp.local.",
    name="office._meshcop._udp.local.",
    addresses=["127.0.0.1", "fe80::10ed:6406:4ee9:85e0"],
    port=8080,
    properties={
        "rv": "1",
        "vn": "Apple",
        "nn": "OpenThread HC",
        "xp": "\xe6\x0f\xc7\xc1\x86!,\xe5",
        "tv": "1.2.0",
        "xa": "\xae\xeb/YKW\x0b\xbf",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
)
# Make sure this generates an invalid DNSPointer
TEST_ZEROCONF_RECORD_4.name = "office._meshcop._udp.lo\x00cal."

# This has no XA
TEST_ZEROCONF_RECORD_5 = ServiceInfo(
    type_="_meshcop._udp.local.",
    name="bad_1._meshcop._udp.local.",
    addresses=["127.0.0.1", "fe80::10ed:6406:4ee9:85e0"],
    port=8080,
    properties={
        "rv": "1",
        "vn": "Apple",
        "nn": "OpenThread HC",
        "xp": "\xe6\x0f\xc7\xc1\x86!,\xe5",
        "tv": "1.2.0",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
)

# This has no XP
TEST_ZEROCONF_RECORD_6 = ServiceInfo(
    type_="_meshcop._udp.local.",
    name="bad_2._meshcop._udp.local.",
    addresses=["127.0.0.1", "fe80::10ed:6406:4ee9:85e0"],
    port=8080,
    properties={
        "rv": "1",
        "vn": "Apple",
        "nn": "OpenThread HC",
        "tv": "1.2.0",
        "xa": "\xae\xeb/YKW\x0b\xbf",
        "sb": "\x00\x00\x01\xb1",
        "at": "\x00\x00\x00\x00\x00\x01\x00\x00",
        "pt": "\x8f\x06Q~",
        "sq": "3",
        "bb": "\xf0\xbf",
        "dn": "DefaultDomain",
    },
)


@dataclasses.dataclass
class MockRoute:
    """A mock iproute2 route table entry."""

    dst: str
    gateway: str | None = None
    nh_gateway: str | None = None
    metrics: int = 100
    priority: int = 100
    family: int = 10
    dst_len: int = 64


@dataclasses.dataclass
class MockNeighbour:
    """A mock iproute2 neighbour cache entry."""

    dst: str
    lladdr: str = "00:00:00:00:00:00"
    state: int = 64
    probes: int = 64


@pytest.fixture
def ndb() -> Mock:
    """Prevent NDB poking the OS route tables."""
    with patch("pyroute2.NDB") as ndb, ndb() as instance:
        instance.neighbours = []
        instance.routes = []
        yield instance


async def test_diagnostics(
    hass: HomeAssistant,
    mock_async_zeroconf: None,
    ndb: Mock,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for thread routers."""
    cache = mock_async_zeroconf.zeroconf.cache = DNSCache()

    now = time.monotonic() * 1000
    cache.async_add_records(
        [
            *TEST_ZEROCONF_RECORD_1.dns_addresses(created=now),
            TEST_ZEROCONF_RECORD_1.dns_service(created=now),
            TEST_ZEROCONF_RECORD_1.dns_text(created=now),
            TEST_ZEROCONF_RECORD_1.dns_pointer(created=now),
        ]
    )
    cache.async_add_records(
        [
            *TEST_ZEROCONF_RECORD_2.dns_addresses(created=now),
            TEST_ZEROCONF_RECORD_2.dns_service(created=now),
            TEST_ZEROCONF_RECORD_2.dns_text(created=now),
            TEST_ZEROCONF_RECORD_2.dns_pointer(created=now),
        ]
    )
    # Test for invalid cache
    cache.async_add_records([TEST_ZEROCONF_RECORD_3.dns_pointer(created=now)])
    # Test for invalid record
    cache.async_add_records(
        [
            *TEST_ZEROCONF_RECORD_4.dns_addresses(created=now),
            TEST_ZEROCONF_RECORD_4.dns_service(created=now),
            TEST_ZEROCONF_RECORD_4.dns_text(created=now),
            TEST_ZEROCONF_RECORD_4.dns_pointer(created=now),
        ]
    )
    # Test for record without xa
    cache.async_add_records(
        [
            *TEST_ZEROCONF_RECORD_5.dns_addresses(created=now),
            TEST_ZEROCONF_RECORD_5.dns_service(created=now),
            TEST_ZEROCONF_RECORD_5.dns_text(created=now),
            TEST_ZEROCONF_RECORD_5.dns_pointer(created=now),
        ]
    )
    # Test for record without xp
    cache.async_add_records(
        [
            *TEST_ZEROCONF_RECORD_6.dns_addresses(created=now),
            TEST_ZEROCONF_RECORD_6.dns_service(created=now),
            TEST_ZEROCONF_RECORD_6.dns_text(created=now),
            TEST_ZEROCONF_RECORD_6.dns_pointer(created=now),
        ]
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    await dataset_store.async_add_dataset(hass, "source", DATASET_1)

    ndb.neighbours.append(
        MockNeighbour(
            dst="fe80::10ed:6406:4ee9:85e5",
        )
    )
    ndb.neighbours.append(
        MockNeighbour(
            dst="fe80::10ed:6406:4ee9:85e4",
        )
    )

    ndb.routes.append(
        MockRoute(
            dst="fd59:86c6:e5a5::",
            gateway="fe80::10ed:6406:4ee9:85e5",
        )
    )

    ndb.routes.append(
        MockRoute(
            dst="fd59:86c6:e5a5::",
            nh_gateway="fe80::10ed:6406:4ee9:85e4",
        )
    )

    # Add a "ghost" route - we don't know a border router on 85e3
    ndb.routes.append(
        MockRoute(
            dst="fd59:86c6:e5a5::",
            nh_gateway="fe80::10ed:6406:4ee9:85e3",
        )
    )

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag == snapshot
