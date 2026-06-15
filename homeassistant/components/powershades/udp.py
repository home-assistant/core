"""Asyncio UDP transport and discovery for PowerShades devices."""

import asyncio
from collections.abc import Callable
import logging
from typing import TypedDict

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .const import (
    DISCOVERY_TIMEOUT,
    OP_GET_DEVICE_NAME,
    OP_GET_SERIAL,
    OP_GET_SHADE_NAME,
    OP_GET_STATUS,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
    UDP_PORT,
)
from .protocol import (
    GET_SHADE_NAME_PAYLOAD,
    StatusReply,
    build_packet,
    parse_device_name_reply,
    parse_header,
    parse_serial_reply,
    parse_shade_name_reply,
    parse_status_reply,
    verify_packet,
)

_LOGGER = logging.getLogger(__name__)

BROADCAST_IP = "255.255.255.255"


class DiscoveredDevice(TypedDict):
    """A device found via UDP broadcast discovery."""

    ip: str
    serial: int
    model: int


class PowerShadesDeviceInfo(TypedDict):
    """Information probed from a device during config flow validation."""

    serial: int
    name: str | None
    model: int


class PowerShadesTimeoutError(Exception):
    """The device did not reply in time."""


class _PowerShadesProtocol(asyncio.DatagramProtocol):
    """Datagram protocol routing replies to pending requests and status pushes."""

    def __init__(self, on_status: Callable[[StatusReply], None]) -> None:
        self._on_status = on_status
        # Keyed by op alone: real shades do not reliably echo the
        # request's sequence (Get Status always replies sequence 1,
        # whatever was sent). Requests on a connection are serialized,
        # so at most one request per op is pending at a time.
        self.pending: dict[int, asyncio.Future[bytes]] = {}

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if not verify_packet(data):
            _LOGGER.debug("Dropping invalid packet from %s: %s", addr[0], data.hex())
            return
        header = parse_header(data)
        if header is None:
            return
        _LOGGER.debug(
            "Received op=0x%02X seq=%d from %s: %s",
            header.op,
            header.sequence,
            addr[0],
            data.hex(),
        )
        fut = self.pending.pop(header.op, None)
        if fut is not None and not fut.done():
            fut.set_result(data)
            return
        # Unsolicited packet — push status updates to the coordinator
        if header.op == OP_GET_STATUS:
            status = parse_status_reply(data)
            if status is not None:
                self._on_status(status)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error received: %s", exc)


class PowerShadesConnection:
    """A single UDP endpoint talking to one PowerShades device."""

    def __init__(self, host: str) -> None:
        """Initialize the connection."""
        self._host = host
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _PowerShadesProtocol | None = None
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._status_callback: Callable[[StatusReply], None] | None = None

    @property
    def host(self) -> str:
        """Return the device IP address."""
        return self._host

    def set_status_callback(self, callback: Callable[[StatusReply], None]) -> None:
        """Set the callback invoked for every received status packet."""
        self._status_callback = callback

    def _handle_status(self, status: StatusReply) -> None:
        if self._status_callback is not None:
            self._status_callback(status)

    async def async_connect(self) -> None:
        """Create the datagram endpoint on an ephemeral local port."""
        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: _PowerShadesProtocol(self._handle_status),
            local_addr=("0.0.0.0", 0),
        )

    def _send(self, op: int, sequence: int, payload: bytes = b"") -> None:
        """Send one packet."""
        if self._transport is None:
            raise PowerShadesTimeoutError("Connection is closed")
        packet = build_packet(op, sequence, payload=payload)
        self._transport.sendto(packet, (self._host, UDP_PORT))
        _LOGGER.debug(
            "Sent op=0x%02X seq=%d to %s:%d: %s",
            op,
            sequence,
            self._host,
            UDP_PORT,
            packet.hex(),
        )

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) % 256
        return self._sequence

    async def async_request(
        self,
        op: int,
        payload: bytes = b"",
        timeout: float = REQUEST_TIMEOUT,
        retries: int = REQUEST_RETRIES,
    ) -> bytes:
        """Send a packet and wait for the reply echoing its op and sequence."""
        if self._protocol is None or self._transport is None:
            raise PowerShadesTimeoutError("Connection is closed")
        async with self._lock:
            # Each attempt still sends a fresh sequence ("adjacent
            # query must be different"), but replies are matched by op
            # only — the device does not echo the sequence on all ops.
            for _attempt in range(retries + 1):
                sequence = self._next_sequence()
                fut: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
                self._protocol.pending[op] = fut
                self._send(op, sequence, payload)
                try:
                    return await asyncio.wait_for(fut, timeout)
                except TimeoutError:
                    pass
                finally:
                    if self._protocol is not None:
                        self._protocol.pending.pop(op, None)
            raise PowerShadesTimeoutError(
                f"No reply to op 0x{op:02X} from {self._host}"
            )

    def close(self) -> None:
        """Close the endpoint."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            self._protocol = None


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    """Collects Get Serial replies during broadcast discovery."""

    def __init__(self, results: dict[str, DiscoveredDevice]) -> None:
        self._results = results

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if not verify_packet(data):
            _LOGGER.debug("Dropping invalid discovery reply from %s", addr[0])
            return
        parsed = parse_serial_reply(data)
        # Key by the packet source address — it is authoritative, the
        # IP embedded in the reply payload is not.
        if parsed is not None and addr[0] not in self._results:
            self._results[addr[0]] = {
                "ip": addr[0],
                "serial": parsed["serial"],
                "model": parsed["model"],
            }
            _LOGGER.debug("Discovered device %s (serial %s)", addr[0], parsed["serial"])

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("Discovery UDP error: %s", exc)


async def async_discover_devices(
    hass: HomeAssistant, timeout: float = DISCOVERY_TIMEOUT
) -> list[DiscoveredDevice]:
    """Discover PowerShades devices via UDP broadcast on all adapters."""
    loop = asyncio.get_running_loop()
    results: dict[str, DiscoveredDevice] = {}
    transports: list[asyncio.DatagramTransport] = []
    packet = build_packet(OP_GET_SERIAL, sequence=0x01)

    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        if not adapter["enabled"]:
            continue
        for ip_info in adapter["ipv4"]:
            try:
                transport, _protocol = await loop.create_datagram_endpoint(
                    lambda: _DiscoveryProtocol(results),
                    local_addr=(ip_info["address"], 0),
                    allow_broadcast=True,
                )
            except OSError as err:
                _LOGGER.debug(
                    "Could not bind discovery socket to %s: %s", ip_info["address"], err
                )
                continue
            transport.sendto(packet, (BROADCAST_IP, UDP_PORT))
            transports.append(transport)

    if not transports:
        _LOGGER.warning("No network adapters available for discovery")
        return []

    try:
        await asyncio.sleep(timeout)
    finally:
        for transport in transports:
            transport.close()

    devices = list(results.values())
    _LOGGER.info("Discovery complete, found %d device(s)", len(devices))
    return devices


async def async_get_device_info(ip_address: str) -> PowerShadesDeviceInfo:
    """Probe a device for its serial number and name.

    Raises PowerShadesTimeoutError if the device does not answer the
    serial request — this is the test-before-configure probe.
    """
    connection = PowerShadesConnection(ip_address)
    await connection.async_connect()
    try:
        reply = await connection.async_request(OP_GET_SERIAL, retries=1)
        parsed = parse_serial_reply(reply)
        if parsed is None:
            raise PowerShadesTimeoutError(f"Malformed serial reply from {ip_address}")

        name = None
        for op, payload, parser in (
            (OP_GET_SHADE_NAME, GET_SHADE_NAME_PAYLOAD, parse_shade_name_reply),
            (OP_GET_DEVICE_NAME, b"", parse_device_name_reply),
        ):
            try:
                name_reply = await connection.async_request(op, payload, retries=0)
            except PowerShadesTimeoutError:
                continue
            name = parser(name_reply)
            if name:
                break

        return {
            "serial": parsed["serial"],
            "name": name,
            "model": parsed["model"],
        }
    finally:
        connection.close()
