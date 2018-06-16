"""Tests for the Sonos config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components import sonos

from tests.common import mock_coro


async def test_creating_entry_sets_up_media_player(hass):
    """Test setting up Sonos loads the media player."""
    with patch('homeassistant.components.media_player.sonos.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            patch('soco.discover', return_value=True):
        result = await hass.config_entries.flow.async_init(sonos.DOMAIN)
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1
