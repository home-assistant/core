"""Tests for the Cast config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.setup import async_setup_component
from homeassistant.components import cast

from tests.common import MockDependency, mock_coro


async def test_creating_entry_sets_up_media_player(hass):
    """Test setting up Cast loads the media player."""
    with patch('homeassistant.components.media_player.cast.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            MockDependency('pychromecast', 'discovery'), \
            patch('pychromecast.discovery.discover_chromecasts',
                  return_value=True):
        result = await hass.config_entries.flow.async_init(
            cast.DOMAIN, context={'source': config_entries.SOURCE_USER})

        # Confirmation form
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'], {})
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_cast_creates_entry(hass):
    """Test that specifying config will create an entry."""
    with patch('homeassistant.components.cast.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            MockDependency('pychromecast', 'discovery'), \
            patch('pychromecast.discovery.discover_chromecasts',
                  return_value=True):
        await async_setup_component(hass, cast.DOMAIN, {
            'cast': {
                'some_config': 'to_trigger_import'
            }
        })
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_cast_not_creates_entry(hass):
    """Test that no config will not create an entry."""
    with patch('homeassistant.components.cast.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup, \
            MockDependency('pychromecast', 'discovery'), \
            patch('pychromecast.discovery.discover_chromecasts',
                  return_value=True):
        await async_setup_component(hass, cast.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
