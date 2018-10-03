"""Test the webhook component."""
from unittest.mock import Mock

import pytest

from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_client(hass, aiohttp_client):
    """Create http client for webhooks."""
    hass.loop.run_until_complete(async_setup_component(hass, 'webhook', {}))
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


async def test_unregistering_webhook(hass, mock_client):
    """Test unregistering a webhook."""
    hooks = []
    webhook_id = hass.components.webhook.async_generate_id()

    async def handle(*args):
        """Handle webhook."""
        hooks.append(args)

    hass.components.webhook.async_register(webhook_id, handle)

    resp = await mock_client.post('/api/webhook/{}'.format(webhook_id))
    assert resp.status == 200
    assert len(hooks) == 1

    hass.components.webhook.async_unregister(webhook_id)

    resp = await mock_client.post('/api/webhook/{}'.format(webhook_id))
    assert resp.status == 200
    assert len(hooks) == 1


async def test_generate_webhook_url(hass):
    """Test we generate a webhook url correctly."""
    hass.config.api = Mock(base_url='https://example.com')
    url = hass.components.webhook.async_generate_url('some_id')

    assert url == 'https://example.com/api/webhook/some_id'


async def test_posting_webhook_nonexisting(hass, mock_client):
    """Test posting to a nonexisting webhook."""
    resp = await mock_client.post('/api/webhook/non-existing')
    assert resp.status == 200


async def test_posting_webhook_invalid_json(hass, mock_client):
    """Test posting to a nonexisting webhook."""
    hass.components.webhook.async_register('hello', None)
    resp = await mock_client.post('/api/webhook/hello', data='not-json')
    assert resp.status == 200


async def test_posting_webhook_json(hass, mock_client):
    """Test posting a webhook with JSON data."""
    hooks = []
    webhook_id = hass.components.webhook.async_generate_id()

    async def handle(*args):
        """Handle webhook."""
        hooks.append((args[0], args[1], await args[2].text()))

    hass.components.webhook.async_register(webhook_id, handle)

    resp = await mock_client.post('/api/webhook/{}'.format(webhook_id), json={
        'data': True
    })
    assert resp.status == 200
    assert len(hooks) == 1
    assert hooks[0][0] is hass
    assert hooks[0][1] == webhook_id
    assert hooks[0][2] == '{"data": true}'


async def test_posting_webhook_no_data(hass, mock_client):
    """Test posting a webhook with no data."""
    hooks = []
    webhook_id = hass.components.webhook.async_generate_id()

    async def handle(*args):
        """Handle webhook."""
        hooks.append(args)

    hass.components.webhook.async_register(webhook_id, handle)

    resp = await mock_client.post('/api/webhook/{}'.format(webhook_id))
    assert resp.status == 200
    assert len(hooks) == 1
    assert hooks[0][0] is hass
    assert hooks[0][1] == webhook_id
    assert await hooks[0][2].text() == ''
