"""Tests for the Sonos config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.setup import async_setup_component
from homeassistant.components import sonos

from tests.common import mock_coro


async def test_creating_entry_sets_up_media_player(hass):
    """Test setting up Sonos loads the media player."""
    with patch('homeassistant.components.media_player.sonos.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            patch('soco.discover', return_value=True):
        result = await hass.config_entries.flow.async_init(
            sonos.DOMAIN, context={'source': config_entries.SOURCE_USER})
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_sonos_creates_entry(hass):
    """Test that specifying config will create an entry."""
    with patch('homeassistant.components.sonos.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            patch('soco.discover', return_value=True):
        await async_setup_component(hass, sonos.DOMAIN, {
            'sonos': {
                'some_config': 'to_trigger_import'
            }
        })
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_sonos_not_creates_entry(hass):
    """Test that no config will not create an entry."""
    with patch('homeassistant.components.sonos.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            patch('soco.discover', return_value=True):
        await async_setup_component(hass, sonos.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
