"""Test the mobile_app_http platform."""
import pytest

from homeassistant.setup import async_setup_component

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.components.mobile_app import (DOMAIN, STORAGE_KEY,
                                                 STORAGE_VERSION,
                                                 CONF_SECRET, CONF_USER_ID)
from homeassistant.core import callback

from tests.common import async_mock_service

FIRE_EVENT = {
    'type': 'fire_event',
    'data': {
        'event_type': 'test_event',
        'event_data': {
            'hello': 'yo world'
        }
    }
}

RENDER_TEMPLATE = {
    'type': 'render_template',
    'data': {
        'template': 'Hello world'
    }
}

CALL_SERVICE = {
    'type': 'call_service',
    'data': {
        'domain': 'test',
        'service': 'mobile_app',
        'service_data': {
            'foo': 'bar'
        }
    }
}

REGISTER = {
    'app_data': {'foo': 'bar'},
    'app_id': 'io.homeassistant.mobile_app_test',
    'app_name': 'Mobile App Tests',
    'app_version': '1.0.0',
    'device_name': 'Test 1',
    'manufacturer': 'mobile_app',
    'model': 'Test',
    'os_version': '1.0',
    'supports_encryption': True
}

UPDATE = {
    'app_data': {'foo': 'bar'},
    'app_version': '2.0.0',
    'device_name': 'Test 1',
    'manufacturer': 'mobile_app',
    'model': 'Test',
    'os_version': '1.0'
}

# pylint: disable=redefined-outer-name


@pytest.fixture
def mobile_app_client(hass, aiohttp_client, hass_storage, hass_admin_user):
    """mobile_app mock client."""
    hass_storage[STORAGE_KEY] = {
        'version': STORAGE_VERSION,
        'data': {
            'mobile_app_test': {
                CONF_SECRET: '58eb127991594dad934d1584bdee5f27',
                'supports_encryption': True,
                CONF_WEBHOOK_ID: 'mobile_app_test',
                'device_name': 'Test Device',
                CONF_USER_ID: hass_admin_user.id,
            }
        }
    }

    assert hass.loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
async def mock_api_client(hass, hass_client):
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    return await hass_client()


async def test_handle_render_template(mobile_app_client):
    """Test that we render templates properly."""
    resp = await mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=RENDER_TEMPLATE
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == {'rendered': 'Hello world'}


async def test_handle_call_services(hass, mobile_app_client):
    """Test that we call services properly."""
    calls = async_mock_service(hass, 'test', 'mobile_app')

    resp = await mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=CALL_SERVICE
    )

    assert resp.status == 200

    assert len(calls) == 1


async def test_handle_fire_event(hass, mobile_app_client):
    """Test that we can fire events."""
    events = []

    @callback
    def store_event(event):
        """Helepr to store events."""
        events.append(event)

    hass.bus.async_listen('test_event', store_event)

    resp = await mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=FIRE_EVENT
    )

    assert resp.status == 200
    text = await resp.text()
    assert text == ""

    assert len(events) == 1
    assert events[0].data['hello'] == 'yo world'


async def test_update_registration(mobile_app_client, hass_client):
    """Test that a we can update an existing registration via webhook."""
    mock_api_client = await hass_client()
    register_resp = await mock_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()

    webhook_id = register_json[CONF_WEBHOOK_ID]

    update_container = {
        'type': 'update_registration',
        'data': UPDATE
    }

    update_resp = await mobile_app_client.post(
        '/api/webhook/{}'.format(webhook_id), json=update_container
    )

    assert update_resp.status == 200
    update_json = await update_resp.json()
    assert update_json['app_version'] == '2.0.0'
    assert CONF_WEBHOOK_ID not in update_json
    assert CONF_SECRET not in update_json


async def test_returns_error_incorrect_json(mobile_app_client, caplog):
    """Test that an error is returned when JSON is invalid."""
    resp = await mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        data='not json'
    )

    assert resp.status == 400
    json = await resp.json()
    assert json == []
    assert 'invalid JSON' in caplog.text


async def test_handle_decryption(mobile_app_client):
    """Test that we can encrypt/decrypt properly."""
    try:
        # pylint: disable=unused-import
        from nacl.secret import SecretBox  # noqa: F401
        from nacl.encoding import Base64Encoder  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    keylen = SecretBox.KEY_SIZE
    key = "58eb127991594dad934d1584bdee5f27".encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b'\0')

    payload = json.dumps({'template': 'Hello world'}).encode("utf-8")

    data = SecretBox(key).encrypt(payload,
                                  encoder=Base64Encoder).decode("utf-8")

    container = {
        'type': 'render_template',
        'encrypted': True,
        'encrypted_data': data,
    }

    resp = await mobile_app_client.post(
        '/api/webhook/mobile_app_test',
        json=container
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == {'rendered': 'Hello world'}


async def test_register_device(hass_client, mock_api_client):
    """Test that a device can be registered."""
    try:
        # pylint: disable=unused-import
        from nacl.secret import SecretBox  # noqa: F401
        from nacl.encoding import Base64Encoder  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    resp = await mock_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert resp.status == 201
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    keylen = SecretBox.KEY_SIZE
    key = register_json[CONF_SECRET].encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b'\0')

    payload = json.dumps({'template': 'Hello world'}).encode("utf-8")

    data = SecretBox(key).encrypt(payload,
                                  encoder=Base64Encoder).decode("utf-8")

    container = {
        'type': 'render_template',
        'encrypted': True,
        'encrypted_data': data,
    }

    mobile_app_client = await hass_client()

    resp = await mobile_app_client.post(
        '/api/webhook/{}'.format(register_json[CONF_WEBHOOK_ID]),
        json=container
    )

    assert resp.status == 200

    webhook_json = await resp.json()
    assert webhook_json == {'rendered': 'Hello world'}
