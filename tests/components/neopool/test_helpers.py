"""Tests for the NeoPool helper functions."""

import asyncio as _asyncio
from datetime import UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from neopool_modbus.exceptions import NeoPoolError
import pytest

from homeassistant.components.neopool.config_flow import is_host_port_open
from homeassistant.components.neopool.helpers import (
    async_get_device_serial,
    calculate_next_interval_time,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def test_calculate_next_interval_time_with_hass(hass: HomeAssistant) -> None:
    """With hass, the next-interval timestamp is in HA's local timezone."""
    hass.config.time_zone = "Europe/Prague"
    result = calculate_next_interval_time(3600, hass)
    assert result is not None
    assert result.tzinfo is not None
    assert result.second == 0
    assert result.microsecond == 0
    expected = (
        dt_util.now(ZoneInfo("Europe/Prague")) + timedelta(seconds=3600)
    ).replace(second=0, microsecond=0)
    assert abs((result - expected).total_seconds()) < 60


def test_calculate_next_interval_time_without_hass() -> None:
    """Without hass, calculation falls back to UTC."""
    result = calculate_next_interval_time(7200, None)
    assert result is not None
    assert result.tzinfo == UTC
    assert result.second == 0
    expected = (dt_util.utcnow() + timedelta(seconds=7200)).replace(
        second=0, microsecond=0
    )
    assert abs((result - expected).total_seconds()) < 60


@pytest.mark.parametrize("invalid", [0, -100, None])
def test_calculate_next_interval_time_invalid_input(invalid: float | None) -> None:
    """Zero, negative or None seconds yield None."""
    assert calculate_next_interval_time(invalid, None) is None


async def test_is_host_port_open_succeeds() -> None:
    """is_host_port_open returns True when asyncio reports a connection."""
    fake_writer = MagicMock()
    fake_writer.close = MagicMock()
    fake_writer.wait_closed = AsyncMock()
    with patch(
        "homeassistant.components.neopool.config_flow.asyncio.open_connection",
        new=AsyncMock(return_value=(MagicMock(), fake_writer)),
    ):
        assert await is_host_port_open("127.0.0.1", 502) is True
    fake_writer.close.assert_called_once()


async def test_is_host_port_open_returns_false_on_oserror() -> None:
    """is_host_port_open returns False when the probe raises OSError."""
    with patch(
        "homeassistant.components.neopool.config_flow.asyncio.open_connection",
        new=AsyncMock(side_effect=OSError("connection refused")),
    ):
        assert await is_host_port_open("127.0.0.1", 1) is False


async def test_is_host_port_open_returns_false_on_timeout() -> None:
    """is_host_port_open returns False when asyncio.wait_for times out."""
    with patch(
        "homeassistant.components.neopool.config_flow.asyncio.wait_for",
        new=AsyncMock(side_effect=TimeoutError),
    ):
        assert await is_host_port_open("127.0.0.1", 1) is False


async def test_async_get_device_serial_success() -> None:
    """async_get_device_serial returns the serial when the probe succeeds."""
    config = {"host": "192.0.2.1", "port": 502, "unit_id": 1, "modbus_framer": "tcp"}
    with patch(
        "homeassistant.components.neopool.helpers.async_probe_serial",
        new=AsyncMock(return_value="ABCDEF1234"),
    ):
        assert await async_get_device_serial(config) == "ABCDEF1234"


async def test_async_get_device_serial_neopool_error_returns_none() -> None:
    """A NeoPoolError from the probe yields None and a warning log entry."""
    config = {"host": "192.0.2.1", "port": 502}
    with patch(
        "homeassistant.components.neopool.helpers.async_probe_serial",
        new=AsyncMock(side_effect=NeoPoolError("connection refused")),
    ):
        assert await async_get_device_serial(config) is None


async def test_async_get_device_serial_propagates_cancelled_error() -> None:
    """async.CancelledError propagates so callers can act on cancellation."""
    config = {"host": "192.0.2.1", "port": 502}
    with (
        patch(
            "homeassistant.components.neopool.helpers.async_probe_serial",
            new=AsyncMock(side_effect=_asyncio.CancelledError),
        ),
        pytest.raises(_asyncio.CancelledError),
    ):
        await async_get_device_serial(config)
