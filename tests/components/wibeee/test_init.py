"""Tests for Wibeee integration setup."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.wibeee.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_flow_init(hass: HomeAssistant) -> None:
    """Test that the flow is initialized."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_config_entry_loaded(loaded_entry: ConfigEntry) -> None:
    """Test that config entry is loaded."""
    assert loaded_entry.state is ConfigEntryState.LOADED
