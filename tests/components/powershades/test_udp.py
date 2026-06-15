"""Tests for the PowerShades UDP transport and discovery."""

import asyncio
import struct
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.powershades import udp as udp_module
from homeassistant.components.powershades.const import (
    OP_GET_DEVICE_NAME,
    OP_GET_SERIAL,
    OP_GET_SHADE_NAME,
    OP_GET_STATUS,
)
from homeassistant.components.powershades.protocol import (
    StatusReply,
    build_packet,
    parse_header,
    parse_status_reply,
)
from homeassistant.components.powershades.udp import (
    PowerShadesConnection,
    PowerShadesTimeoutError,
    _DiscoveryProtocol,
    _PowerShadesProtocol,
    async_discover_devices,
    async_get_device_info,
)
from homeassistant.core import HomeAssistant

from .conftest import shade_name_packet, status_packet


class _FakeDeviceProtocol(asyncio.DatagramProtocol):
    """A minimal fake PowerShades device for loopback tests."""

    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.reply_for: dict[int, bytes] = {}

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        header = parse_header(data)
        if header is None:
            return
        reply = self.reply_for.get(header.op)
        if reply is not None and self.transport is not None:
            self.transport.sendto(reply, addr)

    def error_received(self, exc: Exception) -> None:
        """Ignore errors."""


@pytest.fixture
async def fake_device(socket_enabled: None):
    """A fake PowerShades device listening on loopback."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _FakeDeviceProtocol, local_addr=("127.0.0.1", 0)
    )
    try:
        yield transport, protocol
    finally:
        transport.close()


def _serial_payload(model: int, serial: int) -> bytes:
    payload = struct.pack("<BBBBIIB", model, 0, 0, 0, serial, 0, 0)
    return payload + b"\x00" * (24 - 8 - len(payload))


# --- _PowerShadesProtocol ---------------------------------------------------


def test_protocol_drops_invalid_packet() -> None:
    """An invalid packet is dropped without affecting pending requests."""
    proto = _PowerShadesProtocol(lambda status: None)
    proto.datagram_received(b"not a valid packet", ("1.2.3.4", 42))
    assert proto.pending == {}


async def test_protocol_resolves_pending_future() -> None:
    """A reply matching a pending request resolves its future."""
    proto = _PowerShadesProtocol(lambda status: None)
    fut: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
    proto.pending[OP_GET_STATUS] = fut

    packet = status_packet()
    proto.datagram_received(packet, ("1.2.3.4", 42))

    assert fut.done()
    assert fut.result() == packet


def test_protocol_routes_unsolicited_status() -> None:
    """An unsolicited status packet is routed to the status callback."""
    statuses: list[StatusReply] = []
    proto = _PowerShadesProtocol(statuses.append)

    proto.datagram_received(status_packet(), ("1.2.3.4", 42))

    assert statuses == [StatusReply(position=50, battery_mv=3700)]


def test_protocol_error_received() -> None:
    """Errors are logged and do not raise."""
    proto = _PowerShadesProtocol(lambda status: None)
    proto.error_received(OSError("boom"))


# --- PowerShadesConnection ---------------------------------------------------


def test_connection_host_property() -> None:
    """The host property returns the configured host."""
    connection = PowerShadesConnection("192.168.1.50")
    assert connection.host == "192.168.1.50"


def test_handle_status_without_callback() -> None:
    """A status push with no registered callback is a no-op."""
    connection = PowerShadesConnection("127.0.0.1")
    connection._handle_status(StatusReply(position=50, battery_mv=3700))


def test_handle_status_with_callback() -> None:
    """A status push is forwarded to the registered callback."""
    connection = PowerShadesConnection("127.0.0.1")
    received: list[StatusReply] = []
    connection.set_status_callback(received.append)

    status = StatusReply(position=50, battery_mv=3700)
    connection._handle_status(status)

    assert received == [status]


def test_send_raises_when_not_connected() -> None:
    """Sending before connecting raises PowerShadesTimeoutError."""
    connection = PowerShadesConnection("127.0.0.1")
    with pytest.raises(PowerShadesTimeoutError):
        connection._send(OP_GET_STATUS, 1)


async def test_async_request_before_connect_raises() -> None:
    """Requesting before connecting raises PowerShadesTimeoutError."""
    connection = PowerShadesConnection("127.0.0.1")
    with pytest.raises(PowerShadesTimeoutError):
        await connection.async_request(OP_GET_STATUS)


async def test_async_request_roundtrip(
    monkeypatch: pytest.MonkeyPatch, fake_device
) -> None:
    """A request is sent and the matching reply is returned."""
    transport, protocol = fake_device
    fake_port = transport.get_extra_info("sockname")[1]
    protocol.reply_for[OP_GET_STATUS] = status_packet()
    monkeypatch.setattr(udp_module, "UDP_PORT", fake_port)

    connection = PowerShadesConnection("127.0.0.1")
    await connection.async_connect()
    try:
        reply = await connection.async_request(OP_GET_STATUS)
        assert parse_status_reply(reply) == StatusReply(position=50, battery_mv=3700)
    finally:
        connection.close()


async def test_async_request_timeout_raises(
    monkeypatch: pytest.MonkeyPatch, fake_device
) -> None:
    """A request that never gets a reply raises after exhausting retries."""
    transport, _protocol = fake_device
    fake_port = transport.get_extra_info("sockname")[1]
    monkeypatch.setattr(udp_module, "UDP_PORT", fake_port)

    connection = PowerShadesConnection("127.0.0.1")
    await connection.async_connect()
    try:
        with pytest.raises(PowerShadesTimeoutError):
            await connection.async_request(OP_GET_STATUS, timeout=0.05, retries=1)
    finally:
        connection.close()


# --- _DiscoveryProtocol -------------------------------------------------------


def test_discovery_protocol_drops_invalid_packet() -> None:
    """An invalid discovery reply is dropped."""
    results: dict[str, udp_module.DiscoveredDevice] = {}
    proto = _DiscoveryProtocol(results)
    proto.datagram_received(b"not a valid packet", ("192.168.1.50", 42))
    assert results == {}


def test_discovery_protocol_collects_serial_reply() -> None:
    """A valid serial reply is recorded, keyed by source address."""
    results: dict[str, udp_module.DiscoveredDevice] = {}
    proto = _DiscoveryProtocol(results)

    packet = build_packet(OP_GET_SERIAL, payload=_serial_payload(model=1, serial=12345))
    proto.datagram_received(packet, ("192.168.1.50", 42))

    assert results == {
        "192.168.1.50": {"ip": "192.168.1.50", "serial": 12345, "model": 1}
    }


def test_discovery_protocol_ignores_duplicate_address() -> None:
    """A second reply from an already-seen address is ignored."""
    results: dict[str, udp_module.DiscoveredDevice] = {
        "192.168.1.50": {"ip": "192.168.1.50", "serial": 1, "model": 1}
    }
    proto = _DiscoveryProtocol(results)

    packet = build_packet(OP_GET_SERIAL, payload=_serial_payload(model=9, serial=99999))
    proto.datagram_received(packet, ("192.168.1.50", 42))

    assert results["192.168.1.50"]["serial"] == 1


def test_discovery_protocol_error_received() -> None:
    """Errors are logged and do not raise."""
    _DiscoveryProtocol({}).error_received(OSError("boom"))


# --- async_discover_devices ---------------------------------------------------


async def test_discover_devices_no_adapters(hass: HomeAssistant) -> None:
    """No network adapters means no transports and an empty result."""
    with patch(
        "homeassistant.components.powershades.udp.network.async_get_adapters",
        return_value=[],
    ):
        assert await async_discover_devices(hass, timeout=0.01) == []


async def test_discover_devices_skips_disabled_adapter(hass: HomeAssistant) -> None:
    """A disabled adapter is skipped entirely."""
    adapters = [{"enabled": False, "ipv4": [{"address": "192.168.1.10"}]}]
    with patch(
        "homeassistant.components.powershades.udp.network.async_get_adapters",
        return_value=adapters,
    ):
        assert await async_discover_devices(hass, timeout=0.01) == []


async def test_discover_devices_bind_error_continues(hass: HomeAssistant) -> None:
    """A bind failure on one adapter is logged and discovery continues."""
    adapters = [{"enabled": True, "ipv4": [{"address": "10.255.255.1"}]}]
    mock_loop = Mock()
    mock_loop.create_datagram_endpoint = AsyncMock(side_effect=OSError("bind failed"))
    with (
        patch(
            "homeassistant.components.powershades.udp.network.async_get_adapters",
            return_value=adapters,
        ),
        patch(
            "homeassistant.components.powershades.udp.asyncio.get_running_loop",
            return_value=mock_loop,
        ),
    ):
        assert await async_discover_devices(hass, timeout=0.01) == []


async def test_discover_devices_success(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant, fake_device
) -> None:
    """A device replying to the broadcast probe is discovered."""
    transport, protocol = fake_device
    fake_port = transport.get_extra_info("sockname")[1]
    protocol.reply_for[OP_GET_SERIAL] = build_packet(
        OP_GET_SERIAL, payload=_serial_payload(model=2, serial=54321)
    )
    monkeypatch.setattr(udp_module, "UDP_PORT", fake_port)
    monkeypatch.setattr(udp_module, "BROADCAST_IP", "127.0.0.1")

    adapters = [{"enabled": True, "ipv4": [{"address": "127.0.0.1"}]}]
    with patch(
        "homeassistant.components.powershades.udp.network.async_get_adapters",
        return_value=adapters,
    ):
        result = await async_discover_devices(hass, timeout=0.05)

    assert result == [{"ip": "127.0.0.1", "serial": 54321, "model": 2}]


# --- async_get_device_info ----------------------------------------------------


async def test_async_get_device_info_success(
    monkeypatch: pytest.MonkeyPatch, fake_device
) -> None:
    """A device that answers both the serial and name probes is described."""
    transport, protocol = fake_device
    fake_port = transport.get_extra_info("sockname")[1]
    protocol.reply_for[OP_GET_SERIAL] = build_packet(
        OP_GET_SERIAL, payload=_serial_payload(model=1, serial=12345)
    )
    protocol.reply_for[OP_GET_SHADE_NAME] = shade_name_packet("Bedroom Shade")
    monkeypatch.setattr(udp_module, "UDP_PORT", fake_port)

    info = await async_get_device_info("127.0.0.1")

    assert info == {"serial": 12345, "name": "Bedroom Shade", "model": 1}


async def test_async_get_device_info_malformed_serial_reply(
    monkeypatch: pytest.MonkeyPatch, fake_device
) -> None:
    """A reply too short to be a serial reply raises PowerShadesTimeoutError."""
    transport, protocol = fake_device
    fake_port = transport.get_extra_info("sockname")[1]
    protocol.reply_for[OP_GET_SERIAL] = build_packet(OP_GET_SERIAL, payload=b"\x00" * 4)
    monkeypatch.setattr(udp_module, "UDP_PORT", fake_port)

    with pytest.raises(PowerShadesTimeoutError):
        await async_get_device_info("127.0.0.1")


async def test_async_get_device_info_falls_back_to_device_name(
    monkeypatch: pytest.MonkeyPatch, fake_device
) -> None:
    """If the shade-name probe times out, the device-name probe is tried."""
    transport, protocol = fake_device
    fake_port = transport.get_extra_info("sockname")[1]
    protocol.reply_for[OP_GET_SERIAL] = build_packet(
        OP_GET_SERIAL, payload=_serial_payload(model=1, serial=12345)
    )
    # No reply configured for OP_GET_SHADE_NAME, so that probe times out.
    device_name_payload = b"RF Gateway".ljust(50, b"\x00")
    protocol.reply_for[OP_GET_DEVICE_NAME] = build_packet(
        OP_GET_DEVICE_NAME, payload=device_name_payload
    )
    monkeypatch.setattr(udp_module, "UDP_PORT", fake_port)
    # Shorten the default request timeout so the shade-name probe (which
    # gets no reply) fails quickly instead of waiting REQUEST_TIMEOUT.
    monkeypatch.setattr(
        PowerShadesConnection.async_request, "__defaults__", (b"", 0.05, 2)
    )

    info = await async_get_device_info("127.0.0.1")

    assert info == {"serial": 12345, "name": "RF Gateway", "model": 1}
