"""Test cloud webhooks."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.cloud import prefs, webhooks

from tests.common import mock_coro


@pytest.fixture
def mock_webhooks(hass):
    cloud = Mock()
    cloud.hass = hass
    cloud.hass.async_add_executor_job = Mock(return_value=mock_coro())
    cloud.iot = Mock(async_send_message=Mock(return_value=mock_coro()))
    cloud.webhook_create_url = 'https://webhook-create.url'
    cloud.prefs = prefs.CloudPreferences(hass)
    hass.loop.run_until_complete(cloud.prefs.async_initialize(True))
    return webhooks.Webhooks(cloud)


async def test_enable(mock_webhooks, aioclient_mock):
    """Test enabling webhooks."""
    aioclient_mock.post('https://webhook-create.url', json={
        'webhook_id': 'mock-cloud-id',
        'url': 'https://hooks.nabu.casa/ZXCZCXZ',
    })

    hook = {
            'webhook_id': 'mock-webhook-id',
            'cloud_id': 'mock-cloud-id',
            'cloud_url': 'https://hooks.nabu.casa/ZXCZCXZ',
        }

    assert hook == await mock_webhooks.async_enable('mock-webhook-id')

    assert mock_webhooks.cloud.prefs.webhooks == {
        'mock-webhook-id': hook
    }

    publish_calls = mock_webhooks.cloud.iot.async_send_message.mock_calls
    assert len(publish_calls) == 1
    assert publish_calls[0][1][0] == 'webhook-register'
    assert publish_calls[0][1][1] == {
        'webhook_ids': ['mock-cloud-id']
    }


async def test_disable(mock_webhooks):
    """Test disabling webhooks."""
    mock_webhooks.cloud.prefs._prefs['webhooks'] = {
        'mock-webhook-id': {
            'webhook_id': 'mock-webhook-id',
            'cloud_id': 'mock-cloud-id',
            'cloud_url': 'https://hooks.nabu.casa/ZXCZCXZ',
        }
    }

    await mock_webhooks.async_disable('mock-webhook-id')

    assert mock_webhooks.cloud.prefs.webhooks == {}

    publish_calls = mock_webhooks.cloud.iot.async_send_message.mock_calls
    assert len(publish_calls) == 1
    assert publish_calls[0][1][0] == 'webhook-register'
    assert publish_calls[0][1][1] == {
        'webhook_ids': []
    }
