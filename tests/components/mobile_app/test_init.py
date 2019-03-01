"""Test the mobile_app_http platform."""
import asyncio

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_component, MockConfigEntry

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
    'device_name': 'Test 1',
    'app_id': 'io.homeassistant.mobile_app_test',
    'device_id': 'mobile_app_test',
    'app_version': '1.0.0',
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
                'webhook_id': 'mobile_app_test'
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


async def test_registers_device(hass, hass_client):
    """Test that a device can be registered."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    http_client = await hass_client()

    resp = await http_client.post(
        '/api/mobile_app/register', json=REGISTER
    )

    assert resp.status == 200
    json = await resp.json()
    assert 'webhook_id' in json
    assert 'secret' in json


async def test_no_duplicate_device(hass, hass_client):
    """Test that a device can not be registered twice."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    http_client = await hass_client()

    good_resp = await http_client.post(
        '/api/mobile_app/register', json=REGISTER
    )

    assert good_resp.status == 200
    good_json = await good_resp.json()
    assert 'webhook_id' in good_json
    assert 'secret' in good_json

    bad_resp = await http_client.post(
        '/api/mobile_app/register', json=REGISTER
    )

    assert bad_resp.status == 409


async def test_config_flow_import(hass):
    """Test that we automatically create a config flow."""
    assert not hass.config_entries.async_entries(DOMAIN)
    assert await async_setup_component(hass, DOMAIN, {
        DOMAIN: {

        }
    })
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN)
