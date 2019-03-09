"""Tests for the mobile_app HTTP API."""
# pylint: disable=redefined-outer-name,unused-import
import pytest

from homeassistant.components.mobile_app.const import CONF_SECRET
from homeassistant.const import CONF_WEBHOOK_ID

from .const import REGISTER
from . import authed_api_client  # noqa: F401


async def test_registration(hass_client, authed_api_client):  # noqa: F811
    """Test that registrations happen."""
    try:
        # pylint: disable=unused-import
        from nacl.secret import SecretBox  # noqa: F401
        from nacl.encoding import Base64Encoder  # noqa: F401
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    resp = await authed_api_client.post(
        '/api/mobile_app/registrations', json=REGISTER
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
