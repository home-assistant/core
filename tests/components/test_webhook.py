"""Test the webhook component."""
from unittest.mock import Mock

import pytest

from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_client(hass, hass_client):
    """Create http client for webhooks."""
    hass.loop.run_until_complete(async_setup_component(hass, 'webhook', {}))
    return hass.loop.run_until_complete(hass_client())


async def test_unregistering_webhook(hass, mock_client):
    """Test unregistering a webhook."""
    hooks = []
    webhook_id = hass.components.webhook.async_generate_id()

    async def handle(*args):
        """Handle webhook."""
        hooks.append(args)

    hass.components.webhook.async_register(
        'test', "Test hook", webhook_id, handle)

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
    hass.components.webhook.async_register('test', "Test hook", 'hello', None)
    resp = await mock_client.post('/api/webhook/hello', data='not-json')
    assert resp.status == 200


async def test_posting_webhook_json(hass, mock_client):
    """Test posting a webhook with JSON data."""
    hooks = []
    webhook_id = hass.components.webhook.async_generate_id()

    async def handle(*args):
        """Handle webhook."""
        hooks.append((args[0], args[1], await args[2].text()))

    hass.components.webhook.async_register(
        'test', "Test hook", webhook_id, handle)

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

    hass.components.webhook.async_register(
        'test', "Test hook", webhook_id, handle)

    resp = await mock_client.post('/api/webhook/{}'.format(webhook_id))
    assert resp.status == 200
    assert len(hooks) == 1
    assert hooks[0][0] is hass
    assert hooks[0][1] == webhook_id
    assert await hooks[0][2].text() == ''


async def test_listing_webhook(hass, hass_ws_client, hass_access_token):
    """Test unregistering a webhook."""
    assert await async_setup_component(hass, 'webhook', {})
    client = await hass_ws_client(hass, hass_access_token)

    hass.components.webhook.async_register(
        'test', "Test hook", "my-id", None)

    await client.send_json({
        'id': 5,
        'type': 'webhook/list',
    })

    msg = await client.receive_json()
    assert msg['id'] == 5
    assert msg['success']
    assert msg['result'] == [
        {
            'webhook_id': 'my-id',
            'domain': 'test',
            'name': 'Test hook'
        }
    ]
