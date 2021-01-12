"""Tests for the init module."""
from unittest.mock import Mock, patch

from pyavreceiver.error import AVReceiverIncompatibleDeviceError
import pytest

from homeassistant.components.avreceiver import (
    AVRManager,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.avreceiver.const import DOMAIN, UNSUB_UPDATE_LISTENER
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component


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


async def test_async_setup_entry_loads_platforms(hass, config_entry, controller):
    """Test load connects to avr and loads platforms."""
    config_entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_forward_entry_setup") as forward_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == 1
        assert controller.init.call_count == 1
        controller.disconnect.assert_not_called()
    assert hass.data[DOMAIN][config_entry.entry_id]["controller"]
    assert hass.data[DOMAIN][config_entry.entry_id][MEDIA_PLAYER_DOMAIN]


async def test_async_setup_entry_connect_failure(hass, config_entry, controller):
    """Connection failure raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)
    controller.init.side_effect = AVReceiverIncompatibleDeviceError()
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
    assert controller.init.call_count == 1
    assert controller.disconnect.call_count == 1
    controller.init.reset_mock()
    controller.disconnect.reset_mock()


async def test_unload_entry(hass, config_entry, controller):
    """Test entries are unloaded correctly."""
    controller_manager = Mock(AVRManager)
    hass.data[DOMAIN] = {
        config_entry.entry_id: {
            "controller": controller_manager,
            UNSUB_UPDATE_LISTENER: Mock(),
        }
    }
    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as unload:
        assert await async_unload_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert controller_manager.disconnect.call_count == 1
        assert unload.call_count == 1
    assert config_entry.entry_id not in hass.data[DOMAIN]
