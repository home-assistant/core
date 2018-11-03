"""Test auth of websocket API."""
from unittest.mock import patch

from homeassistant.components.websocket_api.const import URL
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH, TYPE_AUTH_INVALID, TYPE_AUTH_OK, TYPE_AUTH_REQUIRED)

from homeassistant.components.websocket_api import commands
from homeassistant.setup import async_setup_component

from tests.common import mock_coro

from . import API_PASSWORD


async def test_auth_via_msg(no_auth_websocket_client):
    """Test authenticating."""
    await no_auth_websocket_client.send_json({
        'type': TYPE_AUTH,
        'api_password': API_PASSWORD
    })

    msg = await no_auth_websocket_client.receive_json()

    assert msg['type'] == TYPE_AUTH_OK


async def test_auth_via_msg_incorrect_pass(no_auth_websocket_client):
    """Test authenticating."""
    with patch('homeassistant.components.websocket_api.auth.'
               'process_wrong_login', return_value=mock_coro()) \
            as mock_process_wrong_login:
        await no_auth_websocket_client.send_json({
            'type': TYPE_AUTH,
            'api_password': API_PASSWORD + 'wrong'
        })

        msg = await no_auth_websocket_client.receive_json()

    assert mock_process_wrong_login.called
    assert msg['type'] == TYPE_AUTH_INVALID
    assert msg['message'] == 'Invalid access token or password'


async def test_pre_auth_only_auth_allowed(no_auth_websocket_client):
    """Verify that before authentication, only auth messages are allowed."""
    await no_auth_websocket_client.send_json({
        'type': commands.TYPE_CALL_SERVICE,
        'domain': 'domain_test',
        'service': 'test_service',
        'service_data': {
            'hello': 'world'
        }
    })

    msg = await no_auth_websocket_client.receive_json()

    assert msg['type'] == TYPE_AUTH_INVALID
    assert msg['message'].startswith('Auth message incorrectly formatted')


async def test_auth_active_with_token(hass, aiohttp_client, hass_access_token):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.active') as auth_active:
            auth_active.return_value = True
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'access_token': hass_access_token
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_OK


async def test_auth_active_user_inactive(hass, aiohttp_client,
                                         hass_access_token):
    """Test authenticating with a token."""
    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    refresh_token.user.is_active = False
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.active') as auth_active:
            auth_active.return_value = True
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'access_token': hass_access_token
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_INVALID


async def test_auth_active_with_password_not_allow(hass, aiohttp_client):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.active',
                   return_value=True):
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'api_password': API_PASSWORD
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_INVALID


async def test_auth_legacy_support_with_password(hass, aiohttp_client):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.active',
                   return_value=True),\
             patch('homeassistant.auth.AuthManager.support_legacy',
                   return_value=True):
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'api_password': API_PASSWORD
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_OK


async def test_auth_with_invalid_token(hass, aiohttp_client):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.active') as auth_active:
            auth_active.return_value = True
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'access_token': 'incorrect'
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_INVALID
