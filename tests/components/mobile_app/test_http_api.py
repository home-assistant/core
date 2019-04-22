"""Tests for the mobile_app HTTP API."""
# pylint: disable=redefined-outer-name,unused-import
import pytest

from homeassistant.components.mobile_app.const import CONF_SECRET, DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component

from .const import REGISTER, RENDER_TEMPLATE
from . import authed_api_client  # noqa: F401


async def test_registration(hass, hass_client):  # noqa: F811
    """Test that registrations happen."""
    try:
        # pylint: disable=unused-import
        from nacl.secret import SecretBox  # noqa: F401
        from nacl.encoding import Base64Encoder  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    resp = await api_client.post(
        '/api/mobile_app/registrations', json=REGISTER
    )

    assert resp.status == 201
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    entries = hass.config_entries.async_entries(DOMAIN)

    assert entries[0].data['app_data'] == REGISTER['app_data']
    assert entries[0].data['app_id'] == REGISTER['app_id']
    assert entries[0].data['app_name'] == REGISTER['app_name']
    assert entries[0].data['app_version'] == REGISTER['app_version']
    assert entries[0].data['device_name'] == REGISTER['device_name']
    assert entries[0].data['manufacturer'] == REGISTER['manufacturer']
    assert entries[0].data['model'] == REGISTER['model']
    assert entries[0].data['os_name'] == REGISTER['os_name']
    assert entries[0].data['os_version'] == REGISTER['os_version']
    assert entries[0].data['supports_encryption'] == \
        REGISTER['supports_encryption']

    keylen = SecretBox.KEY_SIZE
    key = register_json[CONF_SECRET].encode("utf-8")
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

    resp = await api_client.post(
        '/api/webhook/{}'.format(register_json[CONF_WEBHOOK_ID]),
        json=container
    )

    assert resp.status == 200

    webhook_json = await resp.json()
    assert 'encrypted_data' in webhook_json

    decrypted_data = SecretBox(key).decrypt(webhook_json['encrypted_data'],
                                            encoder=Base64Encoder)
    decrypted_data = decrypted_data.decode("utf-8")

    assert json.loads(decrypted_data) == {'one': 'Hello world'}
