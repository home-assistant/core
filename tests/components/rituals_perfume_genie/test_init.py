"""Tests for the Rituals Perfume Genie integration."""
from unittest.mock import patch

import aiohttp

from homeassistant.components.rituals_perfume_genie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import init_integration, mock_config_entry


async def test_config_entry_not_ready(hass: HomeAssistant):
    """Test the Rituals configuration entry setup if connection to Rituals is missing."""
    config_entry = mock_config_entry(unique_id="id_123_not_ready")
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rituals_perfume_genie.Account.get_devices",
        side_effect=aiohttp.ClientError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_unload(hass: HomeAssistant) -> None:
    """Test the Rituals Perfume Genie configuration entry setup and unloading."""
    config_entry = mock_config_entry(unique_id="id_123_unload")
    await init_integration(hass, config_entry)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]
