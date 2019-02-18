"""The tests the cover command line platform."""
import os
import tempfile
from unittest import mock

import pytest

from homeassistant.components.cover import DOMAIN
import homeassistant.components.cover.command_line as cmd_rs
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER)
from homeassistant.setup import async_setup_component


@pytest.fixture
def rs(hass):
    """Return CommandCover instance."""
    return cmd_rs.CommandCover(hass, 'foo', 'command_open', 'command_close',
                               'command_stop', 'command_state', None)


def test_should_poll_new(rs):
    """Test the setting of polling."""
    assert rs.should_poll is True
    rs._command_state = None
    assert rs.should_poll is False


def test_query_state_value(rs):
    """Test with state value."""
    with mock.patch('subprocess.check_output') as mock_run:
        mock_run.return_value = b' foo bar '
        result = rs._query_state_value('runme')
        assert 'foo bar' == result
        assert mock_run.call_count == 1
        assert mock_run.call_args == mock.call('runme', shell=True)


async def test_state_value(hass):
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, 'cover_status')
        test_cover = {
            'command_state': 'cat {}'.format(path),
            'command_open': 'echo 1 > {}'.format(path),
            'command_close': 'echo 1 > {}'.format(path),
            'command_stop': 'echo 0 > {}'.format(path),
            'value_template': '{{ value }}'
        }
        assert await async_setup_component(hass, DOMAIN, {
            'cover': {
                'platform': 'command_line',
                'covers': {
                    'test': test_cover
                }
            }
        }) is True

        assert 'unknown' == hass.states.get('cover.test').state

        await hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: 'cover.test'}, blocking=True)
        assert 'open' == hass.states.get('cover.test').state

        await hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: 'cover.test'}, blocking=True)
        assert 'open' == hass.states.get('cover.test').state

        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: 'cover.test'}, blocking=True)
        assert 'closed' == hass.states.get('cover.test').state
