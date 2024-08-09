"""Test Emoncms component setup process."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import EMONCMS_FAILURE

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    emoncms_client: AsyncMock,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    emoncms_client: AsyncMock,
) -> None:
    """Test load failure."""
    emoncms_client.async_request.return_value = EMONCMS_FAILURE
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
