"""Tests for the init module."""
import asyncio

from asynctest import patch
from pyheos import CommandError, const
import pytest

from homeassistant.components.heos import (
    SourceManager, async_setup_entry, async_unload_entry)
from homeassistant.components.heos.const import (
    DATA_CONTROLLER, DATA_SOURCE_MANAGER, DOMAIN)
from homeassistant.components.media_player.const import (
    DOMAIN as MEDIA_PLAYER_DOMAIN)
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component


async def test_async_setup_creates_entry(hass, config):
    """Test component setup creates entry from config."""
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == 'Controller (127.0.0.1)'
    assert entry.data == {CONF_HOST: '127.0.0.1'}


async def test_async_setup_updates_entry(hass, config_entry, config):
    """Test component setup updates entry from config."""
    config[DOMAIN][CONF_HOST] = '127.0.0.2'
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == 'Controller (127.0.0.2)'
    assert entry.data == {CONF_HOST: '127.0.0.2'}


async def test_async_setup_returns_true(hass, config_entry, config):
    """Test component setup from config."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0] == config_entry


async def test_async_setup_no_config_returns_true(hass, config_entry):
    """Test component setup from entry only."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0] == config_entry


async def test_async_setup_entry_loads_platforms(
        hass, config_entry, controller):
    """Test load connects to heos, retrieves players, and loads platforms."""
    config_entry.add_to_hass(hass)
    with patch.object(
            hass.config_entries, 'async_forward_entry_setup') as forward_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == 1
        assert controller.connect.call_count == 1
        controller.disconnect.assert_not_called()
    assert hass.data[DOMAIN][DATA_CONTROLLER] == controller
    assert hass.data[DOMAIN][MEDIA_PLAYER_DOMAIN] == controller.players
    assert isinstance(hass.data[DOMAIN][DATA_SOURCE_MANAGER], SourceManager)


async def test_async_setup_entry_connect_failure(
        hass, config_entry, controller):
    """Connection failure raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    errors = [ConnectionError, asyncio.TimeoutError]
    for error in errors:
        controller.connect.side_effect = error
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, config_entry)
            await hass.async_block_till_done()
        assert controller.connect.call_count == 1
        assert controller.disconnect.call_count == 1
        controller.connect.reset_mock()
        controller.disconnect.reset_mock()


async def test_async_setup_entry_player_failure(
        hass, config_entry, controller):
    """Failure to retrieve players/sources raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    errors = [ConnectionError, asyncio.TimeoutError]
    for error in errors:
        controller.get_players.side_effect = error
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, config_entry)
            await hass.async_block_till_done()
        assert controller.connect.call_count == 1
        assert controller.disconnect.call_count == 1
        controller.connect.reset_mock()
        controller.disconnect.reset_mock()


async def test_unload_entry(hass, config_entry, controller):
    """Test entries are unloaded correctly."""
    hass.data[DOMAIN] = {DATA_CONTROLLER: controller}
    with patch.object(hass.config_entries, 'async_forward_entry_unload',
                      return_value=True) as unload:
        assert await async_unload_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert controller.disconnect.call_count == 1
        assert unload.call_count == 1
    assert DOMAIN not in hass.data


async def test_update_sources_retry(hass, config_entry, config, controller,
                                    caplog):
    """Test update sources retries on failures to max attempts."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    controller.get_favorites.reset_mock()
    controller.get_input_sources.reset_mock()
    source_manager = hass.data[DOMAIN][DATA_SOURCE_MANAGER]
    source_manager.retry_delay = 0
    source_manager.max_retry_attempts = 1
    controller.get_favorites.side_effect = CommandError("Test", "test", 0)
    controller.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED)
    # Wait until it's finished
    while "Unable to update sources" not in caplog.text:
        await asyncio.sleep(0.1)
    assert controller.get_favorites.call_count == 2
    assert controller.get_input_sources.call_count == 2
