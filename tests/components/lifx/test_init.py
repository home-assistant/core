"""Tests for the lifx component."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import IP_ADDRESS, MAC_ADDRESS, _patch_config_entry_try_connect, _patch_discovery

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_configuring_lifx_causes_discovery(hass):
    """Test that specifying empty config does discovery."""
    with patch("homeassistant.components.lifx.Discover.discover") as discover:
        discover.return_value = {MagicMock(): MagicMock()}
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        call_count = len(discover.mock_calls)
        assert discover.mock_calls

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(discover.mock_calls) == call_count * 2

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15))
        await hass.async_block_till_done()
        assert len(discover.mock_calls) == call_count * 3

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=30))
        await hass.async_block_till_done()
        assert len(discover.mock_calls) == call_count * 4


async def test_config_entry_reload(hass):
    """Test that a config entry can be reloaded."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_config_entry_try_connect():
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.LOADED
        await hass.config_entries.async_unload(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_retry(hass):
    """Test that a config entry can be retried."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(no_device=True), _patch_config_entry_try_connect(
        no_device=True
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state == ConfigEntryState.SETUP_RETRY
