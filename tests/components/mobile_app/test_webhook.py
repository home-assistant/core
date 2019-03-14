"""Webhook tests for mobile_app."""
# pylint: disable=redefined-outer-name,unused-import
import logging
import pytest

from homeassistant.components.mobile_app.const import CONF_SECRET
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback

from tests.common import async_mock_service

from . import (authed_api_client, create_registrations,  # noqa: F401
               webhook_client)  # noqa: F401

from .const import (CALL_SERVICE, FIRE_EVENT, REGISTER_CLEARTEXT,
                    RENDER_TEMPLATE, UPDATE)

_LOGGER = logging.getLogger(__name__)


async def test_webhook_handle_render_template(create_registrations,  # noqa: F401, F811, E501
                                              webhook_client):  # noqa: F811
    """Test that we render templates properly."""
    resp = await webhook_client.post(
        '/api/webhook/{}'.format(create_registrations[1]['webhook_id']),
        json=RENDER_TEMPLATE
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == {'one': 'Hello world'}


async def test_webhook_handle_call_services(hass, create_registrations,  # noqa: F401, F811, E501
                                            webhook_client):  # noqa: E501 F811
    """Test that we call services properly."""
    calls = async_mock_service(hass, 'test', 'mobile_app')

    resp = await webhook_client.post(
        '/api/webhook/{}'.format(create_registrations[1]['webhook_id']),
        json=CALL_SERVICE
    )

    assert resp.status == 200

    assert len(calls) == 1


async def test_webhook_handle_fire_event(hass, create_registrations,  # noqa: F401, F811, E501
                                         webhook_client):  # noqa: F811
    """Test that we can fire events."""
    events = []

    @callback
    def store_event(event):
        """Helepr to store events."""
        events.append(event)

    hass.bus.async_listen('test_event', store_event)

    resp = await webhook_client.post(
        '/api/webhook/{}'.format(create_registrations[1]['webhook_id']),
        json=FIRE_EVENT
    )

    assert resp.status == 200
    json = await resp.json()
    assert json == {}

    assert len(events) == 1
    assert events[0].data['hello'] == 'yo world'


async def test_webhook_update_registration(webhook_client, hass_client):  # noqa: E501 F811
    """Test that a we can update an existing registration via webhook."""
    authed_api_client = await hass_client()  # noqa: F811
    register_resp = await authed_api_client.post(
        '/api/mobile_app/registrations', json=REGISTER_CLEARTEXT
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


async def test_webhook_returns_error_incorrect_json(webhook_client,  # noqa: F401, F811, E501
                                                    create_registrations,  # noqa: F401, F811, E501
                                                    caplog):  # noqa: E501 F811
    """Test that an error is returned when JSON is invalid."""
    resp = await webhook_client.post(
        '/api/webhook/{}'.format(create_registrations[1]['webhook_id']),
        data='not json'
    )

    assert resp.status == 400
    json = await resp.json()
    assert json == {}
    assert 'invalid JSON' in caplog.text


async def test_webhook_handle_decryption(webhook_client,  # noqa: F811
                                         create_registrations):  # noqa: F401, F811, E501
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
    key = create_registrations[0]['secret'].encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b'\0')

    payload = json.dumps(RENDER_TEMPLATE['data']).encode("utf-8")

    data = SecretBox(key).encrypt(payload,
                                  encoder=Base64Encoder).decode("utf-8")

    container = {
        'type': 'render_template',
        'encrypted': True,
        'encrypted_data': data,
    }

    resp = await webhook_client.post(
        '/api/webhook/{}'.format(create_registrations[0]['webhook_id']),
        json=container
    )

    assert resp.status == 200

    webhook_json = await resp.json()
    assert 'encrypted_data' in webhook_json

    decrypted_data = SecretBox(key).decrypt(webhook_json['encrypted_data'],
                                            encoder=Base64Encoder)
    decrypted_data = decrypted_data.decode("utf-8")

    assert json.loads(decrypted_data) == {'one': 'Hello world'}


async def test_webhook_requires_encryption(webhook_client,  # noqa: F811
                                           create_registrations):  # noqa: F401, F811, E501
    """Test that encrypted registrations only accept encrypted data."""
    resp = await webhook_client.post(
        '/api/webhook/{}'.format(create_registrations[0]['webhook_id']),
        json=RENDER_TEMPLATE
    )

    assert resp.status == 400

    webhook_json = await resp.json()
    assert 'error' in webhook_json
    assert webhook_json['success'] is False
    assert webhook_json['error']['code'] == 'encryption_required'
