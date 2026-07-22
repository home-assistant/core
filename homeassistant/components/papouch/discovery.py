"""File used for discovering Papouch devices on the local network."""

# TODO:

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


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


async def async_discover_papouch_devices() -> list[str]:
    """Broadcast discovery request and return a list of found IP addresses."""
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(
        PapouchDiscoveryProtocol,
        local_addr=("0.0.0.0", 0),
        allow_broadcast=True,
    )

    await asyncio.sleep(2)
    transport.close()

    return list(protocol.discovered_ips)
