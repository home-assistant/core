"""Test cloud cloudhooks."""
from unittest.mock import Mock

import pytest

from homeassistant.components.cloud import prefs, cloudhooks

from tests.common import mock_coro


@pytest.fixture
def mock_cloudhooks(hass):
    """Mock cloudhooks class."""
    cloud = Mock()
    cloud.hass = hass
    cloud.hass.async_add_executor_job = Mock(return_value=mock_coro())
    cloud.iot = Mock(async_send_message=Mock(return_value=mock_coro()))
    cloud.cloudhook_create_url = 'https://webhook-create.url'
    cloud.prefs = prefs.CloudPreferences(hass)
    hass.loop.run_until_complete(cloud.prefs.async_initialize())
    return cloudhooks.Cloudhooks(cloud)


async def test_enable(mock_cloudhooks, aioclient_mock):
    """Test enabling cloudhooks."""
    aioclient_mock.post('https://webhook-create.url', json={
        'cloudhook_id': 'mock-cloud-id',
        'url': 'https://hooks.nabu.casa/ZXCZCXZ',
    })

    hook = {
            'webhook_id': 'mock-webhook-id',
            'cloudhook_id': 'mock-cloud-id',
            'cloudhook_url': 'https://hooks.nabu.casa/ZXCZCXZ',
        }

    assert hook == await mock_cloudhooks.async_create('mock-webhook-id')

    assert mock_cloudhooks.cloud.prefs.cloudhooks == {
        'mock-webhook-id': hook
    }

    publish_calls = mock_cloudhooks.cloud.iot.async_send_message.mock_calls
    assert len(publish_calls) == 1
    assert publish_calls[0][1][0] == 'webhook-register'
    assert publish_calls[0][1][1] == {
        'cloudhook_ids': ['mock-cloud-id']
    }


async def test_disable(mock_cloudhooks):
    """Test disabling cloudhooks."""
    mock_cloudhooks.cloud.prefs._prefs['cloudhooks'] = {
        'mock-webhook-id': {
            'webhook_id': 'mock-webhook-id',
            'cloudhook_id': 'mock-cloud-id',
            'cloudhook_url': 'https://hooks.nabu.casa/ZXCZCXZ',
        }
    }

    await mock_cloudhooks.async_delete('mock-webhook-id')

    assert mock_cloudhooks.cloud.prefs.cloudhooks == {}

    publish_calls = mock_cloudhooks.cloud.iot.async_send_message.mock_calls
    assert len(publish_calls) == 1
    assert publish_calls[0][1][0] == 'webhook-register'
    assert publish_calls[0][1][1] == {
        'cloudhook_ids': []
    }
