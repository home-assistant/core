"""File used for discovering Papouch devices on the local network."""

import asyncio
import logging
from typing import cast, override

from aiopapouch import PapouchHTTPClient, is_device_supported
from aiopapouch.exceptions import DeviceAuthError, DeviceConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

ACTIVE_DISCOVERY_TIMEOUT = 2
MAGIC_PACKET = b"\x00\x00\x00\xf6"
TARGET_PORT = 30718
SEMAPHORE_COUNTER = 5

_LOGGER = logging.getLogger(__name__)


class PapouchDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol implementation for broadcasting and receiving Papouch discovery packets."""

    def __init__(self) -> None:
        """Initialize the protocol with the required magic packet and target port."""
        self.magic_packet = MAGIC_PACKET
        self.target_port = TARGET_PORT
        self.discovered_ips: set[str] = set()
        self.transport: asyncio.DatagramTransport | None = None

    @override
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Send the magic broadcast packet when the UDP connection is established."""
        self.transport = cast(asyncio.DatagramTransport, transport)
        self.transport.sendto(self.magic_packet, ("255.255.255.255", self.target_port))

    @override
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Process incoming replies from Papouch devices."""
        ip_address = addr[0]
        self.discovered_ips.add(ip_address)


async def _get_device_info(
    hass: HomeAssistant, ip_address: str
) -> tuple[str, str] | None:
    """Return tuple (location, name) of the device.

    If it is an unsupported device the function returns None.
    """

    session = async_get_clientsession(hass)
    client = PapouchHTTPClient(ip_address, session)

    try:
        device_name, device_location = await client.get_device_info()
    except (DeviceConnectionError, DeviceAuthError) as err:
        _LOGGER.debug("Could not get device info from %s: %s", ip_address, err)
        return None
    else:
        if not is_device_supported(device_name):
            return None

        if device_name is None or device_location is None:
            return None

        return (device_location, device_name)


async def async_discover_papouch_devices(
    hass: HomeAssistant,
) -> dict[str, tuple[str, str]]:
    """Broadcast discovery request and return a dictionary of discovered devices.

    Creates semaphore preventing network congestion and fail-safe timeout that
    will destroy the session afterwards.

    Returns:
        A dictionary mapping IP addresses to a tuple containing (location, name)
    """
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(
        PapouchDiscoveryProtocol,
        local_addr=("0.0.0.0", 0),
        allow_broadcast=True,
    )

    await asyncio.sleep(ACTIVE_DISCOVERY_TIMEOUT)
    transport.close()

    raw_ips = list(protocol.discovered_ips)
    semaphore = asyncio.Semaphore(SEMAPHORE_COUNTER)

    async def _safe_check(ip: str) -> tuple[str, tuple[str, str] | None]:
        async with semaphore:
            try:
                async with asyncio.timeout(ACTIVE_DISCOVERY_TIMEOUT):
                    data = await _get_device_info(hass, ip)
                    return (ip, data)
            except TimeoutError:
                return (ip, None)

    results = await asyncio.gather(*[_safe_check(ip) for ip in raw_ips])
    return {ip: data for ip, data in results if data is not None}
