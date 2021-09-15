"""Tests for the Poolstation integration."""
from unittest.mock import patch

import aiohttp

from homeassistant.components.poolstation.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import init_integration, mock_config_entry


async def test_config_entry_not_ready(hass: HomeAssistant):
    """Test the Poolstation configuration entry setup if connection to Poolstation is missing."""
    config_entry = mock_config_entry(uniqe_id="id_my_pool_not_ready")
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.poolstation.Pool.get_all_pools",
        side_effect=aiohttp.ClientError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_unload(hass: HomeAssistant) -> None:
    """Test the Poolstation configuration entry setup and unloading."""
    config_entry = mock_config_entry(uniqe_id="id_my_pool_unload")
    with patch(
        "homeassistant.components.poolstation.Pool.get_all_pools",
        return_value=[],
    ):
        await init_integration(hass, config_entry)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]
