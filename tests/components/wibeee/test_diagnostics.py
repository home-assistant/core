"""Tests for Wibeee diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.wibeee.diagnostics import (
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
    mock_wibeee_api.async_get_push_server_config.return_value = {
        "mac": "00:11:22:33:44:55"
    }
    mock_wibeee_api.async_fetch_device_diagnostics.return_value = {"host": "1.2.3.4"}

    diag = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert diag["device"]["mac_addr"] == REDACTED
    assert diag["device_config"]["host"] == REDACTED
    assert diag["push_server_config"]["mac"] == REDACTED


async def test_diagnostics_error(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test diagnostics handles API errors."""
    mock_wibeee_api.async_get_push_server_config.side_effect = Exception("API Error")
    mock_wibeee_api.async_fetch_device_diagnostics.side_effect = Exception("API Error")

    diag = await async_get_config_entry_diagnostics(hass, loaded_entry)

    assert "error" in diag["push_server_config"]
    assert "error" in diag["device_config"]
