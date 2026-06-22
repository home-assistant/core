"""Tests for iTach client helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from pyitach import ItachClient, ItachConnectionError
import pytest

from homeassistant.components.itach.client import (
    async_create_client,
    async_send_command,
    command_to_gc_timings,
    raw_timing_to_gc_cycles,
)
from homeassistant.components.itach.command import ParsedItachCommand


def test_raw_timing_to_gc_cycles() -> None:
    """Test converting raw microsecond timings to Global Caché cycles."""
    assert raw_timing_to_gc_cycles(1000, 38000) == 38
    assert raw_timing_to_gc_cycles(500, 38000) == 19


def test_raw_timing_to_gc_cycles_has_minimum_of_one() -> None:
    """Test conversion never returns less than one cycle."""
    assert raw_timing_to_gc_cycles(1, 38000) == 1


def test_command_to_gc_timings() -> None:
    """Test converting a parsed command to Global Caché timings."""
    command = ParsedItachCommand(modulation=38000, timings=[1000, 500, 1, 20])

    assert command_to_gc_timings(command) == [38, 19, 1, 1]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_create_client() -> None:
    """Test creating and connecting a pyitach client."""
    with patch("homeassistant.components.itach.client.ItachClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_connect = AsyncMock()
        mock_client.close = AsyncMock()

        client = await async_create_client("192.168.1.50", 4998, 5.0)

    assert client is mock_client
    mock_client_cls.assert_called_once_with("192.168.1.50", 4998, timeout=5.0)
    mock_client.async_connect.assert_awaited_once_with()
    mock_client.close.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_create_client_closes_on_itach_error() -> None:
    """Test client is closed when connecting raises an iTach error."""
    with patch("homeassistant.components.itach.client.ItachClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_connect = AsyncMock(
            side_effect=ItachConnectionError("cannot connect")
        )
        mock_client.close = AsyncMock()

        with pytest.raises(ItachConnectionError):
            await async_create_client("192.168.1.50", 4998, 5.0)

    mock_client.close.assert_awaited_once_with()


async def test_async_send_command() -> None:
    """Test sending a parsed command through pyitach."""
    mock_client: Any = Mock(spec=ItachClient)
    mock_client.async_send_ir = AsyncMock()
    command = ParsedItachCommand(modulation=38000, timings=[1000, 500])

    await async_send_command(mock_client, 1, 2, command, 3)

    mock_client.async_send_ir.assert_awaited_once_with(
        1,
        2,
        38000,
        [38, 19],
        repeat=3,
    )
