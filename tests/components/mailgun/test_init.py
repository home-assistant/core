"""Test the init file of Mailgun."""
import hashlib
import hmac
from unittest.mock import patch, Mock

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import mailgun
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN

from homeassistant.core import callback
from homeassistant.setup import async_setup_component

API_KEY = 'abc123'
mailgun_events = []


@pytest.fixture
async def fixture(hass, aiohttp_client):
    """Initialize a Home Assistant Server for testing this module."""

    await async_setup_component(hass, mailgun.DOMAIN, {
        mailgun.DOMAIN: {
            CONF_API_KEY: API_KEY,
            CONF_DOMAIN: 'example.com'
        },
    })

    hass.config.api = Mock(base_url='http://example.com')
    result = await hass.config_entries.flow.async_init('mailgun', context={
        'source': 'user'
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    webhook_id = result['result'].data['webhook_id']

    @callback
    def handle_event(event):
        """Handle Mailgun event."""
        mailgun_events.append(event)

    hass.bus.async_listen(mailgun.MESSAGE_RECEIVED, handle_event)

    return await aiohttp_client(hass.http.app), webhook_id


async def test_mailgun_webhook_with_missing_signature(fixture):
    client, webhook_id = fixture

    event_count = len(mailgun_events)

    await client.post('/api/webhook/{}'.format(webhook_id), json={
        'hello': 'mailgun',
        'signature': {}
    })

    assert len(mailgun_events) == event_count

    await client.post('/api/webhook/{}'.format(webhook_id), json={
        'hello': 'mailgun',
    })

    assert len(mailgun_events) == event_count


async def test_mailgun_webhook_with_different_api_key(fixture):
    client, webhook_id = fixture

    timestamp = '1529006854'
    token = 'a8ce0edb2dd8301dee6c2405235584e45aa91d1e9f979f3de0'

    event_count = len(mailgun_events)

    await client.post('/api/webhook/{}'.format(webhook_id), json={
        'hello': 'mailgun',
        'signature': {
            'signature': hmac.new(
                key=b'random_api_key',
                msg=bytes('{}{}'.format(timestamp, token), 'utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest(),
            'timestamp': timestamp,
            'token': token
        }
    })

    assert len(mailgun_events) == event_count


async def test_mailgun_webhook_with_correct_api_key(fixture):
    client, webhook_id = fixture

    timestamp = '1529006854'
    token = 'a8ce0edb2dd8301dee6c2405235584e45aa91d1e9f979f3de0'

    event_count = len(mailgun_events)

    await client.post('/api/webhook/{}'.format(webhook_id), json={
        'hello': 'mailgun',
        'signature': {
            'signature': hmac.new(
                key=bytes(API_KEY, 'utf-8'),
                msg=bytes('{}{}'.format(timestamp, token), 'utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest(),
            'timestamp': timestamp,
            'token': token
        }
    })

    assert len(mailgun_events) == event_count + 1
    assert mailgun_events[-1].data['webhook_id'] == webhook_id
    assert mailgun_events[-1].data['hello'] == 'mailgun'
