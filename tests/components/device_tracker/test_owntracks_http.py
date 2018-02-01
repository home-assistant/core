"""Test the owntracks_http platform."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_coro, mock_component


@pytest.fixture
def mock_client(hass, test_client):
    """Start the Hass HTTP component."""
    mock_component(hass, 'group')
    mock_component(hass, 'zone')
    with patch('homeassistant.components.device_tracker.async_load_config',
               return_value=mock_coro([])):
        hass.loop.run_until_complete(
            async_setup_component(hass, 'device_tracker', {
                'device_tracker': {
                    'platform': 'owntracks_http'
                }
            }))
    return hass.loop.run_until_complete(test_client(hass.http.app))


@pytest.fixture
def mock_handle_message():
    """Mock async_handle_message."""
    with patch('homeassistant.components.device_tracker.'
               'owntracks_http.async_handle_message') as mock:
        mock.return_value = mock_coro(None)
        yield mock


@asyncio.coroutine
def test_forward_message_correctly(mock_client, mock_handle_message):
    """Test that we forward messages correctly to OwnTracks handle message."""
    resp = yield from mock_client.post('/api/owntracks/user/device', json={
        '_type': 'test'
    })
    assert resp.status == 200
    assert len(mock_handle_message.mock_calls) == 1

    data = mock_handle_message.mock_calls[0][1][2]
    assert data == {
        '_type': 'test',
        'topic': 'owntracks/user/device'
    }


@asyncio.coroutine
def test_handle_value_error(mock_client, mock_handle_message):
    """Test that we handle errors from handle message correctly."""
    mock_handle_message.side_effect = ValueError
    resp = yield from mock_client.post('/api/owntracks/user/device', json={
        '_type': 'test'
    })
    assert resp.status == 500
