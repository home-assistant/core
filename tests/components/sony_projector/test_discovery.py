"""Tests for passive discovery of Sony projectors."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sony_projector import discovery
from homeassistant.components.sony_projector.const import (
    CONF_MODEL,
    CONF_SERIAL,
    CONF_TITLE,
    DATA_DISCOVERY,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant


def _sdap_payload(
    *, product: str = "VPL-Test", serial: int = 123456, location: str = "Main"
) -> bytes:
    """Create a minimal SDCP discovery packet."""

    product_bytes = product.encode("ascii").ljust(12, b"\x00")
    return (
        b"PJ"  # id
        b"\x01\x00"  # version, category
        b"HOME"  # community
        + product_bytes
        + struct.pack(">I", serial)
        + struct.pack(">H", 1)
        + location.encode("ascii")
    )


@pytest.mark.parametrize("serial", [123456, 0])
async def test_datagram_triggers_flow(hass: HomeAssistant, serial: int) -> None:
    """Verify an SDCP datagram starts a discovery flow."""

    protocol = discovery.SonyProjectorDiscoveryProtocol(hass)

    with patch(
        "homeassistant.components.sony_projector.discovery.discovery_flow.async_create_flow",
        autospec=True,
    ) as mock_flow:
        protocol.datagram_received(_sdap_payload(serial=serial), ("192.0.2.40", 1000))

    mock_flow.assert_called_once()
    _, _, kwargs = mock_flow.mock_calls[0]
    data = kwargs["data"]
    assert data[CONF_MODEL] == "VPL-Test"
    expected_serial = str(serial) if serial else None
    assert data[CONF_SERIAL] == expected_serial
    assert data[CONF_TITLE] == ("VPL-Test" if serial else DEFAULT_NAME)


async def test_datagram_dedupes_by_device(hass: HomeAssistant) -> None:
    """Ensure repeated broadcasts from the same projector are ignored."""

    protocol = discovery.SonyProjectorDiscoveryProtocol(hass)

    with patch(
        "homeassistant.components.sony_projector.discovery.discovery_flow.async_create_flow",
        autospec=True,
    ) as mock_flow:
        packet = _sdap_payload(serial=54321)
        protocol.datagram_received(packet, ("192.0.2.41", 1000))
        protocol.datagram_received(packet, ("192.0.2.41", 1000))

    mock_flow.assert_called_once()


async def test_invalid_datagram_ignored(hass: HomeAssistant) -> None:
    """Ensure non-SDAP traffic is ignored."""

    protocol = discovery.SonyProjectorDiscoveryProtocol(hass)

    with patch(
        "homeassistant.components.sony_projector.discovery.discovery_flow.async_create_flow",
        autospec=True,
    ) as mock_flow:
        protocol.datagram_received(b"not a projector", ("192.0.2.42", 1000))

    mock_flow.assert_not_called()


async def test_async_start_listener_registers_transport(hass: HomeAssistant) -> None:
    """Ensure the passive listener binds to the SDCP port."""

    mock_transport = MagicMock()
    created_protocol: discovery.SonyProjectorDiscoveryProtocol | None = None

    async def fake_create_datagram_endpoint(factory, **kwargs):
        nonlocal created_protocol
        created_protocol = factory()
        created_protocol.connection_made(mock_transport)
        return mock_transport, created_protocol

    loop = MagicMock()
    loop.create_datagram_endpoint = AsyncMock(side_effect=fake_create_datagram_endpoint)

    with patch("asyncio.get_running_loop", return_value=loop):
        protocol = await discovery.async_start_listener(hass)

    assert protocol is created_protocol
    loop.create_datagram_endpoint.assert_awaited_once()
    assert hass.data[DOMAIN][DATA_DISCOVERY] is protocol
