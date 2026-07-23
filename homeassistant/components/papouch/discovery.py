"""File used for discovering Papouch devices on the local network."""

import asyncio

import aiohttp
from aiopapouch import PapouchApiClient, create_device

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class PapouchDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol implementation for broadcasting and receiving Papouch discovery packets."""

    def __init__(self) -> None:
        """Initialize the protocol with the required magic packet and target port."""
        self.magic_packet = b"\x00\x00\x00\xf6"
        self.target_port = 30718
        self.discovered_ips: set[str] = set()
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Send the magic broadcast packet when the UDP connection is established."""
        self.transport = transport
        transport.sendto(self.magic_packet, ("255.255.255.255", self.target_port))

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Process incoming replies from Papouch devices."""
        ip_address = addr[0]
        self.discovered_ips.add(ip_address)


async def _is_supported_device(
    hass: HomeAssistant, ip_address: str
) -> tuple[str, str] | None:
    """Return location and name of the device.

    If it is an unsupported device the fuction returns None.
    """

    session = async_get_clientsession(hass)
    client = PapouchApiClient(ip_address, session)

    try:
        await client.fetch_info()
        device = await create_device(client)

        if device is None:
            return None

        location = device.get_location()
        name = device.get_name()
        return (location, name)  # noqa: TRY300
    except aiohttp.ClientError:
        return None


async def async_discover_papouch_devices(
    hass: HomeAssistant,
) -> dict[str, tuple[str, str]]:
    """Broadcast discovery request and return a dectionary.

    "ip_address": ("location", "name")
    """
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(
        PapouchDiscoveryProtocol,
        local_addr=("0.0.0.0", 0),
        allow_broadcast=True,
    )

    await asyncio.sleep(2)
    transport.close()

    raw_ips = list(protocol.discovered_ips)
    semaphore = asyncio.Semaphore(5)

    async def _safe_check(ip: str):
        async with semaphore:
            try:
                async with asyncio.timeout(2.0):
                    data = await _is_supported_device(hass, ip)
                    return (ip, data)
            except TimeoutError:
                return (ip, None)

    results = await asyncio.gather(*[_safe_check(ip) for ip in raw_ips])
    return {ip: data for ip, data in results if data is not None}
