"""Tests for Wibeee diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.wibeee.diagnostics import (
    _redact_coordinator_data,
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test diagnostics."""
    mock_wibeee_api.async_fetch_device_diagnostics.return_value = {"host": "1.2.3.4"}

    diag = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert diag["device"]["mac_addr"] == REDACTED
    assert diag["device_config"]["host"] == REDACTED
    assert "entry" in diag
    assert "coordinator" in diag
    assert "push_server_config" not in diag


async def test_diagnostics_error(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test diagnostics handles API errors."""
    mock_wibeee_api.async_fetch_device_diagnostics.side_effect = Exception("API Error")

    diag = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert "error" in diag["device_config"]


def test_redact_coordinator_data_none() -> None:
    """Test _redact_coordinator_data returns None for None input."""
    assert _redact_coordinator_data(None) is None
