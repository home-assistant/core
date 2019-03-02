"""Test the mobile_app_http platform."""
import asyncio

import pytest

from homeassistant.setup import async_setup_component

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.components.mobile_app import (DOMAIN, STORAGE_KEY,
                                                 STORAGE_VERSION)

FIRE_EVENT = {
    'type': 'fire_event',
    'data': {
        'event_type': 'test_event'
    }
}

RENDER_TEMPLATE = {
    'type': 'render_template',
    'data': {
        'template': 'Hello world'
    }
}

REGISTER = {
    'app_id': 'io.homeassistant.mobile_app_test',
    'app_name': 'Mobile App Tests',
    'app_version': '1.0.0',
    'device_name': 'Test 1',
    'integration_data': {'foo': 'bar'},
    'manufacturer': 'mobile_app',
    'model': 'Test',
    'os_version': '1.0',
    'supports_encryption': True
}


@pytest.fixture
def mobile_app_client(hass, aiohttp_client, hass_storage):
    """mobile_app mock client."""
    hass_storage[STORAGE_KEY] = {
        'version': STORAGE_VERSION,
        'data': {
            'mobile_app_test': {
                'secret': '58eb127991594dad934d1584bdee5f27',
                'supports_encryption': True,
                'webhook_id': 'mobile_app_test',
                'device_name': 'Test Device'
            }
        }
    }

    assert hass.loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@asyncio.coroutine
def test_handle_render_template(mobile_app_client):
    """Test that we render templates properly."""
    resp = yield from mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=RENDER_TEMPLATE
    )

    assert resp.status == 200

    json = yield from resp.json()
    assert json == {'rendered': 'Hello world'}


@asyncio.coroutine
def test_handle_fire_event(mobile_app_client):
    """Test that we can fire events."""
    resp = yield from mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=FIRE_EVENT
    )

    assert resp.status == 200
    text = yield from resp.text()
    assert text == ""


@asyncio.coroutine
def test_returns_error_incorrect_json(mobile_app_client, caplog):
    """Test that an error is returned when JSON is invalid."""
    resp = yield from mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        data='not json'
    )

    assert resp.status == 400
    json = yield from resp.json()
    assert json == []
    assert 'invalid JSON' in caplog.text


@asyncio.coroutine
def test_handle_encryption(mobile_app_client):
    """Test that we can encrypt/decrypt properly."""
    import json
    from nacl.secret import SecretBox
    from nacl.encoding import Base64Encoder

    keylen = SecretBox.KEY_SIZE
    key = "58eb127991594dad934d1584bdee5f27".encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b'\0')

    payload = json.dumps({'template': 'Hello world'}).encode("utf-8")

    data = SecretBox(key).encrypt(payload,
                                  encoder=Base64Encoder).decode("utf-8")

    RENDER_TEMPLATE = {
        'type': 'render_template',
        'encrypted': True,
        'encrypted_data': data,
    }

    resp = yield from mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=RENDER_TEMPLATE
    )

    assert resp.status == 200

    json = yield from resp.json()
    assert json == {'rendered': 'Hello world'}


@pytest.fixture
async def mock_api_client(hass, hass_client):
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    return await hass_client()


async def test_register_device(mock_api_client):
    """Test that a device can be registered."""
    resp = await mock_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert resp.status == 201
    json = await resp.json()
    assert 'webhook_id' in json
    assert 'secret' in json


async def test_get_device(mock_api_client):
    """Test that a we can get a device payload."""
    register_resp = await mock_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()

    webhook_id = register_json[CONF_WEBHOOK_ID]

    get_resp = await mock_api_client.get(
        '/api/mobile_app/devices/{}'.format(webhook_id)
    )

    assert get_resp.status == 200
    json = await get_resp.json()
    assert json == REGISTER


async def test_update_device(mock_api_client):
    """Test that a we can update an existing device."""
    register_resp = await mock_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()

    webhook_id = register_json[CONF_WEBHOOK_ID]

    update = REGISTER
    update['app_version'] = '2.0.0'

    put_resp = await mock_api_client.put(
        '/api/mobile_app/devices/{}'.format(webhook_id), json=update
    )

    assert put_resp.status == 200
    put_json = await put_resp.json()
    assert put_json['app_version'] == '2.0.0'
    assert 'webhook_id' not in put_json
    assert 'secret' not in put_json

    get_resp = await mock_api_client.get(
        '/api/mobile_app/devices/{}'.format(webhook_id)
    )

    assert get_resp.status == 200
    get_json = await get_resp.json()
    assert get_json['app_version'] == '2.0.0'
