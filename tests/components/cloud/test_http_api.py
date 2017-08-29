"""Tests for the HTTP API for the cloud component."""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.cloud import DOMAIN, cloud_api

from tests.common import mock_coro


@pytest.fixture
def cloud_client(hass, test_client):
    """Fixture that can fetch from the cloud client."""
    hass.loop.run_until_complete(async_setup_component(hass, 'cloud', {
        'cloud': {
            'mode': 'development'
        }
    }))
    return hass.loop.run_until_complete(test_client(hass.http.app))


@asyncio.coroutine
def test_account_view_no_account(cloud_client):
    """Test fetching account if no account available."""
    req = yield from cloud_client.get('/api/cloud/account')
    assert req.status == 400


@asyncio.coroutine
def test_account_view(hass, cloud_client):
    """Test fetching account if no account available."""
    cloud = MagicMock(account={'test': 'account'})
    hass.data[DOMAIN]['cloud'] = cloud
    req = yield from cloud_client.get('/api/cloud/account')
    assert req.status == 200
    result = yield from req.json()
    assert result == {'test': 'account'}


@asyncio.coroutine
def test_login_view(hass, cloud_client):
    """Test logging in."""
    cloud = MagicMock(account={'test': 'account'})
    cloud.async_refresh_account_info.return_value = mock_coro(None)

    with patch.object(cloud_api, 'async_login',
                      MagicMock(return_value=mock_coro(cloud))):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'username': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 200

    result = yield from req.json()
    assert result == {'test': 'account'}
    assert hass.data[DOMAIN]['cloud'] is cloud


@asyncio.coroutine
def test_login_view_invalid_json(hass, cloud_client):
    """Try logging in with invalid JSON."""
    req = yield from cloud_client.post('/api/cloud/login', data='Not JSON')
    assert req.status == 400
    assert 'cloud' not in hass.data[DOMAIN]


@asyncio.coroutine
def test_login_view_invalid_schema(hass, cloud_client):
    """Try logging in with invalid schema."""
    req = yield from cloud_client.post('/api/cloud/login', json={
        'invalid': 'schema'
    })
    assert req.status == 400
    assert 'cloud' not in hass.data[DOMAIN]


@asyncio.coroutine
def test_login_view_request_timeout(hass, cloud_client):
    """Test request timeout while trying to log in."""
    with patch.object(cloud_api, 'async_login',
                      MagicMock(side_effect=asyncio.TimeoutError)):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'username': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 502
    assert 'cloud' not in hass.data[DOMAIN]


@asyncio.coroutine
def test_login_view_invalid_credentials(hass, cloud_client):
    """Test logging in with invalid credentials."""
    with patch.object(cloud_api, 'async_login',
                      MagicMock(side_effect=cloud_api.Unauthenticated)):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'username': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 401
    assert 'cloud' not in hass.data[DOMAIN]


@asyncio.coroutine
def test_login_view_unknown_error(hass, cloud_client):
    """Test unknown error while logging in."""
    with patch.object(cloud_api, 'async_login',
                      MagicMock(side_effect=cloud_api.UnknownError)):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'username': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 500
    assert 'cloud' not in hass.data[DOMAIN]


@asyncio.coroutine
def test_logout_view(hass, cloud_client):
    """Test logging out."""
    cloud = MagicMock()
    cloud.async_revoke_access_token.return_value = mock_coro(None)
    hass.data[DOMAIN]['cloud'] = cloud

    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 200
    data = yield from req.json()
    assert data == {'result': 'ok'}
    assert 'cloud' not in hass.data[DOMAIN]


@asyncio.coroutine
def test_logout_view_request_timeout(hass, cloud_client):
    """Test timeout while logging out."""
    cloud = MagicMock()
    cloud.async_revoke_access_token.side_effect = asyncio.TimeoutError
    hass.data[DOMAIN]['cloud'] = cloud

    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 502
    assert 'cloud' in hass.data[DOMAIN]


@asyncio.coroutine
def test_logout_view_unknown_error(hass, cloud_client):
    """Test unknown error while loggin out."""
    cloud = MagicMock()
    cloud.async_revoke_access_token.side_effect = cloud_api.UnknownError
    hass.data[DOMAIN]['cloud'] = cloud

    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 502
    assert 'cloud' in hass.data[DOMAIN]
