"""Tests for the steamist component."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.components import steamist
from homeassistant.components.steamist.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_ASYNC_GET_STATUS_ACTIVE, _async_setup_entry_with_status

from tests.common import MockConfigEntry


async def test_config_entry_reload(hass: HomeAssistant) -> None:
    """Test that a config entry can be reloaded."""
    _, config_entry = await _async_setup_entry_with_status(
        hass, MOCK_ASYNC_GET_STATUS_ACTIVE
    )
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_retry_later(hass: HomeAssistant) -> None:
    """Test that a config entry retry on connection error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.steamist.Steamist.async_get_status",
        side_effect=asyncio.TimeoutError,
    ):
        await async_setup_component(hass, steamist.DOMAIN, {steamist.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
