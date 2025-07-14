"""The tests for the zeroconf WebSocket API."""

import asyncio
import socket
from unittest.mock import patch

from zeroconf import (
    DNSAddress,
    DNSPointer,
    DNSService,
    DNSText,
    RecordUpdate,
    const,
    current_time_millis,
)

from homeassistant.components.zeroconf import DOMAIN, async_get_async_instance
from homeassistant.core import HomeAssistant
from homeassistant.generated import zeroconf as zc_gen
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_subscribe_discovery(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test zeroconf subscribe_discovery."""
    instance = await async_get_async_instance(hass)
    instance.zeroconf.cache.async_add_records(
        [
            DNSPointer(
                "_fakeservice._tcp.local.",
                const._TYPE_PTR,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                "wrong._wrongservice._tcp.local.",
            ),
            DNSPointer(
                "_fakeservice._tcp.local.",
                const._TYPE_PTR,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                "foo2._fakeservice._tcp.local.",
            ),
            DNSService(
                "foo2._fakeservice._tcp.local.",
                const._TYPE_SRV,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                0,
                0,
                1234,
                "foo2.local.",
            ),
            DNSAddress(
                "foo2.local.",
                const._TYPE_A,
                const._CLASS_IN,
                const._DNS_HOST_TTL,
                socket.inet_aton("127.0.0.1"),
            ),
            DNSText(
                "foo2.local.",
                const._TYPE_TXT,
                const._CLASS_IN,
                const._DNS_HOST_TTL,
                b"\x13md=HASS Bridge W9DN\x06pv=1.0\x14id=11:8E:DB:5B:5C:C5"
                b"\x05c#=12\x04s#=1",
            ),
            DNSPointer(
                "_fakeservice._tcp.local.",
                const._TYPE_PTR,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                "foo3._fakeservice._tcp.local.",
            ),
            DNSService(
                "foo3._fakeservice._tcp.local.",
                const._TYPE_SRV,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                0,
                0,
                1234,
                "foo3.local.",
            ),
            DNSText(
                "foo3.local.",
                const._TYPE_TXT,
                const._CLASS_IN,
                const._DNS_HOST_TTL,
                b"\x13md=HASS Bridge W9DN\x06pv=1.0\x14id=11:8E:DB:5B:5C:C5"
                b"\x05c#=12\x04s#=1",
            ),
        ]
    )
    with patch.dict(
        zc_gen.ZEROCONF,
        {"_fakeservice._tcp.local.": []},
        clear=True,
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "zeroconf/subscribe_discovery",
        }
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["success"]

    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "ip_addresses": ["127.0.0.1"],
                "name": "foo2._fakeservice._tcp.local.",
                "port": 1234,
                "properties": {},
                "type": "_fakeservice._tcp.local.",
            }
        ]
    }

    # now late inject the address record
    records = [
        DNSAddress(
            "foo3.local.",
            const._TYPE_A,
            const._CLASS_IN,
            const._DNS_HOST_TTL,
            socket.inet_aton("127.0.0.1"),
        ),
    ]
    instance.zeroconf.cache.async_add_records(records)
    instance.zeroconf.record_manager.async_updates(
        current_time_millis(),
        [RecordUpdate(record, None) for record in records],
    )
    # Now for the add
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "ip_addresses": ["127.0.0.1"],
                "name": "foo3._fakeservice._tcp.local.",
                "port": 1234,
                "properties": {},
                "type": "_fakeservice._tcp.local.",
            }
        ]
    }
    # Now for the update
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "ip_addresses": ["127.0.0.1"],
                "name": "foo3._fakeservice._tcp.local.",
                "port": 1234,
                "properties": {},
                "type": "_fakeservice._tcp.local.",
            }
        ]
    }

    # now move time forward and remove the record
    future = current_time_millis() + (4500 * 1000)
    records = instance.zeroconf.cache.async_expire(future)
    record_updates = [RecordUpdate(record, record) for record in records]
    instance.zeroconf.record_manager.async_updates(future, record_updates)
    instance.zeroconf.record_manager.async_updates_complete(True)

    removes: set[str] = set()
    for _ in range(3):
        async with asyncio.timeout(1):
            response = await client.receive_json()
        assert "remove" in response["event"]
        removes.add(next(iter(response["event"]["remove"]))["name"])

    assert len(removes) == 3
    assert removes == {
        "foo2._fakeservice._tcp.local.",
        "foo3._fakeservice._tcp.local.",
        "wrong._wrongservice._tcp.local.",
    }
