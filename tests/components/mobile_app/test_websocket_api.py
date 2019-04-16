"""Test the mobile_app websocket API."""
# pylint: disable=redefined-outer-name,unused-import
from homeassistant.components.mobile_app.const import (CONF_SECRET, DOMAIN)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component

from . import authed_api_client, setup_ws, webhook_client  # noqa: F401
from .const import (CALL_SERVICE, REGISTER)


async def test_webocket_get_user_registrations(hass, aiohttp_client,
                                               hass_ws_client,
                                               hass_read_only_access_token):
    """Test get_user_registrations websocket command from admin perspective."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    user_api_client = await aiohttp_client(hass.http.app, headers={
        'Authorization': "Bearer {}".format(hass_read_only_access_token)
    })

    # First a read only user registers.
    register_resp = await user_api_client.post(
        '/api/mobile_app/registrations', json=REGISTER
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    # Then the admin user attempts to access it.
    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'mobile_app/get_user_registrations',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert len(msg['result']) == 1


async def test_webocket_delete_registration(hass, hass_client,
                                            hass_ws_client, webhook_client):  # noqa: E501 F811
    """Test delete_registration websocket command."""
    authed_api_client = await hass_client()  # noqa: F811
    register_resp = await authed_api_client.post(
        '/api/mobile_app/registrations', json=REGISTER
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
