"""Test the mobile_app platform."""
import pytest

from asynctest import patch

from homeassistant.setup import async_setup_component

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.components.mobile_app.const import (ATTR_DELETED_IDS,
                                                       ATTR_REGISTRATIONS,
                                                       CONF_CLOUDHOOK_ID,
                                                       CONF_CLOUDHOOK_URL,
                                                       CONF_SECRET,
                                                       CONF_USER_ID, DOMAIN,
                                                       HTTP_X_CLOUD_HOOK_ID,
                                                       HTTP_X_CLOUD_HOOK_URL,
                                                       STORAGE_KEY,
                                                       STORAGE_VERSION)
from homeassistant.components.websocket_api.const import TYPE_RESULT

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
def webhook_client(hass, aiohttp_client, hass_storage, hass_admin_user):
    """mobile_app mock client."""
    hass_storage[STORAGE_KEY] = {
        'version': STORAGE_VERSION,
        'data': {
            ATTR_REGISTRATIONS: {
                'mobile_app_test': {
                    CONF_SECRET: '58eb127991594dad934d1584bdee5f27',
                    'supports_encryption': True,
                    CONF_WEBHOOK_ID: 'mobile_app_test',
                    'device_name': 'Test Device',
                    CONF_USER_ID: hass_admin_user.id,
                }
            },
            ATTR_DELETED_IDS: [],
        }
    }

    assert hass.loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
async def authed_api_client(hass, hass_client):
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    return await hass_client()


async def test_handle_render_template(webhook_client):
    """Test that we render templates properly."""
    resp = await webhook_client.post(
        '/api/webhook/mobile_app_test',
        json=RENDER_TEMPLATE
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == {'rendered': 'Hello world'}


async def test_handle_call_services(hass, webhook_client):
    """Test that we call services properly."""
    calls = async_mock_service(hass, 'test', 'mobile_app')

    resp = await webhook_client.post(
        '/api/webhook/mobile_app_test',
        json=CALL_SERVICE
    )

    assert resp.status == 200

    assert len(calls) == 1


async def test_handle_fire_event(hass, webhook_client):
    """Test that we can fire events."""
    events = []

    @callback
    def store_event(event):
        """Helepr to store events."""
        events.append(event)

    hass.bus.async_listen('test_event', store_event)

    resp = await webhook_client.post(
        '/api/webhook/mobile_app_test',
        json=FIRE_EVENT
    )

    assert resp.status == 200
    json = await resp.json()
    assert json == {}

    assert len(events) == 1
    assert events[0].data['hello'] == 'yo world'


async def test_update_registration(webhook_client, hass_client):
    """Test that a we can update an existing registration via webhook."""
    authed_api_client = await hass_client()
    register_resp = await authed_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()

    webhook_id = register_json[CONF_WEBHOOK_ID]

    update_container = {
        'type': 'update_registration',
        'data': UPDATE
    }

    update_resp = await webhook_client.post(
        '/api/webhook/{}'.format(webhook_id), json=update_container
    )

    assert update_resp.status == 200
    update_json = await update_resp.json()
    assert update_json['app_version'] == '2.0.0'
    assert CONF_WEBHOOK_ID not in update_json
    assert CONF_SECRET not in update_json


async def test_returns_error_incorrect_json(webhook_client, caplog):
    """Test that an error is returned when JSON is invalid."""
    resp = await webhook_client.post(
        '/api/webhook/mobile_app_test',
        data='not json'
    )

    assert resp.status == 400
    json = await resp.json()
    assert json == []
    assert 'invalid JSON' in caplog.text


async def test_handle_decryption(webhook_client):
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

    resp = await webhook_client.post(
        '/api/webhook/mobile_app_test',
        json=container
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == {'rendered': 'Hello world'}


async def test_register_device(hass_client, authed_api_client):
    """Test that a device can be registered."""
    try:
        # pylint: disable=unused-import
        from nacl.secret import SecretBox  # noqa: F401
        from nacl.encoding import Base64Encoder  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    resp = await authed_api_client.post(
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

    webhook_client = await hass_client()

    resp = await webhook_client.post(
        '/api/webhook/{}'.format(register_json[CONF_WEBHOOK_ID]),
        json=container
    )

    assert resp.status == 200

    webhook_json = await resp.json()
    assert webhook_json == {'rendered': 'Hello world'}


async def mock_create_cloudhook(hass, webhook_id):
    """Return a mock cloudhook create payload."""
    return {
        CONF_CLOUDHOOK_ID: 'mock-cloud-id',
        CONF_CLOUDHOOK_URL: 'https://hooks.nabu.casa/ZXCZCXZ',
    }


def mock_cloud_logged_in(hass):
    """Return logged in state (true)."""
    return True


@patch('homeassistant.components.mobile_app.webhook.async_create_cloudhook',
       mock_create_cloudhook)
@patch('homeassistant.components.mobile_app.webhook.async_is_logged_in',
       mock_cloud_logged_in)
async def test_cloud_forwarding(hass, hass_client, authed_api_client):
    """Test that a local webhook provides a cloud URL in responses."""
    resp = await authed_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert resp.status == 201
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json
    assert CONF_CLOUDHOOK_ID not in register_json
    assert CONF_CLOUDHOOK_URL not in register_json

    local_url = register_json[CONF_WEBHOOK_ID]

    webhook_client = await hass_client()

    resp = await webhook_client.post(
        '/api/webhook/{}'.format(local_url),
        json=FIRE_EVENT
    )

    assert resp.status == 200

    assert resp.headers[HTTP_X_CLOUD_HOOK_ID] == 'mock-cloud-id'
    assert resp.headers[HTTP_X_CLOUD_HOOK_URL] == \
        'https://hooks.nabu.casa/ZXCZCXZ'


async def test_webocket_get_registration(hass, authed_api_client,
                                         hass_ws_client):
    """Test get_registration websocket command."""
    register_resp = await authed_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'mobile_app/get_registration',
        CONF_WEBHOOK_ID: register_json[CONF_WEBHOOK_ID],
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result']['app_id'] == 'io.homeassistant.mobile_app_test'


async def test_webocket_delete_registration(hass, hass_client,
                                            hass_ws_client, webhook_client):
    """Test delete_registration websocket command."""
    authed_api_client = await hass_client()
    register_resp = await authed_api_client.post(
        '/api/mobile_app/devices', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    webhook_id = register_json[CONF_WEBHOOK_ID]

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'mobile_app/delete_registration',
        CONF_WEBHOOK_ID: webhook_id,
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result'] == 'ok'

    ensure_four_ten_gone = await webhook_client.post(
        '/api/webhook/{}'.format(webhook_id), json=CALL_SERVICE
    )

    assert ensure_four_ten_gone.status == 410
