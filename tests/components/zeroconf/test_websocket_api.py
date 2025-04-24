"""The tests for the bluetooth WebSocket API."""

import asyncio
import socket

from zeroconf import DNSAddress, DNSPointer, DNSService, DNSText, const

from homeassistant.components.zeroconf import DOMAIN, async_get_async_instance
from homeassistant.core import HomeAssistant
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
                "_hap._udp.local.",
                const._TYPE_PTR,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                "foo2._hap._udp.local.",
            ),
            DNSService(
                "foo2._hap._udp.local.",
                const._TYPE_SRV,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                0,
                0,
                1234,
                "foo.local.",
            ),
            DNSAddress(
                "foo.local.",
                const._TYPE_A,
                const._CLASS_IN,
                const._DNS_HOST_TTL,
                socket.inet_aton("127.0.0.1"),
            ),
            DNSText(
                "foo.local.",
                const._TYPE_TXT,
                const._CLASS_IN,
                const._DNS_HOST_TTL,
                b"\x13md=HASS Bridge W9DN\x06pv=1.0\x14id=11:8E:DB:5B:5C:C5\x05c#=12\x04s#=1",
            ),
            DNSPointer(
                "_hap._udp.local.",
                const._TYPE_PTR,
                const._CLASS_IN,
                const._DNS_OTHER_TTL,
                "foo3._hap._udp.local.",
            ),
            DNSService(
                "foo3._hap._udp.local.",
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
                b"\x13md=HASS Bridge W9DN\x06pv=1.0\x14id=11:8E:DB:5B:5C:C5\x05c#=12\x04s#=1",
            ),
        ]
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
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
                "name": "foo2._hap._udp.local.",
                "port": 1234,
                "properties": {},
                "type": "_hap._udp.local.",
            }
        ]
    }

    # now late inject the address record
    instance.zeroconf.cache.async_add_records(
        [
            DNSAddress(
                "foo.local.",
                const._TYPE_A,
                const._CLASS_IN,
                const._DNS_HOST_TTL,
                socket.inet_aton("127.0.0.1"),
            ),
        ]
    )
    async with asyncio.timeout(1):
        response = await client.receive_json()
    assert response["event"] == {
        "add": [
            {
                "ip_addresses": ["127.0.0.1"],
                "name": "foo3._hap._udp.local.",
                "port": 1234,
                "properties": {},
                "type": "_hap._udp.local.",
            }
        ]
    }
