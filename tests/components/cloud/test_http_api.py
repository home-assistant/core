"""Tests for the HTTP API for the cloud component."""
import asyncio
from unittest.mock import patch, MagicMock

import pytest
from jose import jwt

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.cloud import DOMAIN, auth_api, iot

from tests.common import mock_coro


@pytest.fixture
def cloud_client(hass, test_client):
    """Fixture that can fetch from the cloud client."""
    with patch('homeassistant.components.cloud.Cloud.initialize',
               return_value=mock_coro(True)):
        hass.loop.run_until_complete(async_setup_component(hass, 'cloud', {
            'cloud': {
                'mode': 'development',
                'cognito_client_id': 'cognito_client_id',
                'user_pool_id': 'user_pool_id',
                'region': 'region',
                'relayer': 'relayer',
            }
        }))
    hass.data['cloud']._decode_claims = \
        lambda token: jwt.get_unverified_claims(token)
    with patch('homeassistant.components.cloud.Cloud.write_user_info'):
        yield hass.loop.run_until_complete(test_client(hass.http.app))


@pytest.fixture
def mock_cognito():
    """Mock warrant."""
    with patch('homeassistant.components.cloud.auth_api._cognito') as mock_cog:
        yield mock_cog()


@asyncio.coroutine
def test_account_view_no_account(cloud_client):
    """Test fetching account if no account available."""
    req = yield from cloud_client.get('/api/cloud/account')
    assert req.status == 400


@asyncio.coroutine
def test_account_view(hass, cloud_client):
    """Test fetching account if no account available."""
    hass.data[DOMAIN].id_token = jwt.encode({
        'email': 'hello@home-assistant.io',
        'custom:sub-exp': '2018-01-03'
    }, 'test')
    hass.data[DOMAIN].iot.state = iot.STATE_CONNECTED
    req = yield from cloud_client.get('/api/cloud/account')
    assert req.status == 200
    result = yield from req.json()
    assert result == {
        'email': 'hello@home-assistant.io',
        'sub_exp': '2018-01-03',
        'cloud': iot.STATE_CONNECTED,
    }


@asyncio.coroutine
def test_login_view(hass, cloud_client, mock_cognito):
    """Test logging in."""
    mock_cognito.id_token = jwt.encode({
        'email': 'hello@home-assistant.io',
        'custom:sub-exp': '2018-01-03'
    }, 'test')
    mock_cognito.access_token = 'access_token'
    mock_cognito.refresh_token = 'refresh_token'

    with patch('homeassistant.components.cloud.iot.CloudIoT.'
               'connect') as mock_connect, \
            patch('homeassistant.components.cloud.auth_api._authenticate',
                  return_value=mock_cognito) as mock_auth:
        req = yield from cloud_client.post('/api/cloud/login', json={
            'email': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 200
    result = yield from req.json()
    assert result['email'] == 'hello@home-assistant.io'
    assert result['sub_exp'] == '2018-01-03'

    assert len(mock_connect.mock_calls) == 1

    assert len(mock_auth.mock_calls) == 1
    cloud, result_user, result_pass = mock_auth.mock_calls[0][1]
    assert result_user == 'my_username'
    assert result_pass == 'my_password'


@asyncio.coroutine
def test_login_view_invalid_json(cloud_client):
    """Try logging in with invalid JSON."""
    with patch('homeassistant.components.cloud.auth_api.login') as mock_login:
        req = yield from cloud_client.post('/api/cloud/login', data='Not JSON')
    assert req.status == 400
    assert len(mock_login.mock_calls) == 0


@asyncio.coroutine
def test_login_view_invalid_schema(cloud_client):
    """Try logging in with invalid schema."""
    with patch('homeassistant.components.cloud.auth_api.login') as mock_login:
        req = yield from cloud_client.post('/api/cloud/login', json={
            'invalid': 'schema'
        })
    assert req.status == 400
    assert len(mock_login.mock_calls) == 0


@asyncio.coroutine
def test_login_view_request_timeout(cloud_client):
    """Test request timeout while trying to log in."""
    with patch('homeassistant.components.cloud.auth_api.login',
               side_effect=asyncio.TimeoutError):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'email': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 502


@asyncio.coroutine
def test_login_view_invalid_credentials(cloud_client):
    """Test logging in with invalid credentials."""
    with patch('homeassistant.components.cloud.auth_api.login',
               side_effect=auth_api.Unauthenticated):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'email': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 401


@asyncio.coroutine
def test_login_view_unknown_error(cloud_client):
    """Test unknown error while logging in."""
    with patch('homeassistant.components.cloud.auth_api.login',
               side_effect=auth_api.UnknownError):
        req = yield from cloud_client.post('/api/cloud/login', json={
            'email': 'my_username',
            'password': 'my_password'
        })

    assert req.status == 502


@asyncio.coroutine
def test_logout_view(hass, cloud_client):
    """Test logging out."""
    cloud = hass.data['cloud'] = MagicMock()
    cloud.logout.return_value = mock_coro()
    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 200
    data = yield from req.json()
    assert data == {'message': 'ok'}
    assert len(cloud.logout.mock_calls) == 1


@asyncio.coroutine
def test_logout_view_request_timeout(hass, cloud_client):
    """Test timeout while logging out."""
    cloud = hass.data['cloud'] = MagicMock()
    cloud.logout.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 502


@asyncio.coroutine
def test_logout_view_unknown_error(hass, cloud_client):
    """Test unknown error while logging out."""
    cloud = hass.data['cloud'] = MagicMock()
    cloud.logout.side_effect = auth_api.UnknownError
    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 502


@asyncio.coroutine
def test_register_view(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/register', json={
        'email': 'hello@bla.com',
        'password': 'falcon42'
    })
    assert req.status == 200
    assert len(mock_cognito.register.mock_calls) == 1
    result_email, result_pass = mock_cognito.register.mock_calls[0][1]
    assert result_email == 'hello@bla.com'
    assert result_pass == 'falcon42'


@asyncio.coroutine
def test_register_view_bad_data(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/register', json={
        'email': 'hello@bla.com',
        'not_password': 'falcon'
    })
    assert req.status == 400
    assert len(mock_cognito.logout.mock_calls) == 0


@asyncio.coroutine
def test_register_view_request_timeout(mock_cognito, cloud_client):
    """Test timeout while logging out."""
    mock_cognito.register.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/register', json={
        'email': 'hello@bla.com',
        'password': 'falcon42'
    })
    assert req.status == 502


@asyncio.coroutine
def test_register_view_unknown_error(mock_cognito, cloud_client):
    """Test unknown error while logging out."""
    mock_cognito.register.side_effect = auth_api.UnknownError
    req = yield from cloud_client.post('/api/cloud/register', json={
        'email': 'hello@bla.com',
        'password': 'falcon42'
    })
    assert req.status == 502


@asyncio.coroutine
def test_confirm_register_view(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/confirm_register', json={
        'email': 'hello@bla.com',
        'confirmation_code': '123456'
    })
    assert req.status == 200
    assert len(mock_cognito.confirm_sign_up.mock_calls) == 1
    result_code, result_email = mock_cognito.confirm_sign_up.mock_calls[0][1]
    assert result_email == 'hello@bla.com'
    assert result_code == '123456'


@asyncio.coroutine
def test_confirm_register_view_bad_data(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/confirm_register', json={
        'email': 'hello@bla.com',
        'not_confirmation_code': '123456'
    })
    assert req.status == 400
    assert len(mock_cognito.confirm_sign_up.mock_calls) == 0


@asyncio.coroutine
def test_confirm_register_view_request_timeout(mock_cognito, cloud_client):
    """Test timeout while logging out."""
    mock_cognito.confirm_sign_up.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/confirm_register', json={
        'email': 'hello@bla.com',
        'confirmation_code': '123456'
    })
    assert req.status == 502


@asyncio.coroutine
def test_confirm_register_view_unknown_error(mock_cognito, cloud_client):
    """Test unknown error while logging out."""
    mock_cognito.confirm_sign_up.side_effect = auth_api.UnknownError
    req = yield from cloud_client.post('/api/cloud/confirm_register', json={
        'email': 'hello@bla.com',
        'confirmation_code': '123456'
    })
    assert req.status == 502


@asyncio.coroutine
def test_forgot_password_view(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/forgot_password', json={
        'email': 'hello@bla.com',
    })
    assert req.status == 200
    assert len(mock_cognito.initiate_forgot_password.mock_calls) == 1


@asyncio.coroutine
def test_forgot_password_view_bad_data(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/forgot_password', json={
        'not_email': 'hello@bla.com',
    })
    assert req.status == 400
    assert len(mock_cognito.initiate_forgot_password.mock_calls) == 0


@asyncio.coroutine
def test_forgot_password_view_request_timeout(mock_cognito, cloud_client):
    """Test timeout while logging out."""
    mock_cognito.initiate_forgot_password.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/forgot_password', json={
        'email': 'hello@bla.com',
    })
    assert req.status == 502


@asyncio.coroutine
def test_forgot_password_view_unknown_error(mock_cognito, cloud_client):
    """Test unknown error while logging out."""
    mock_cognito.initiate_forgot_password.side_effect = auth_api.UnknownError
    req = yield from cloud_client.post('/api/cloud/forgot_password', json={
        'email': 'hello@bla.com',
    })
    assert req.status == 502


@asyncio.coroutine
def test_resend_confirm_view(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/resend_confirm', json={
        'email': 'hello@bla.com',
    })
    assert req.status == 200
    assert len(mock_cognito.client.resend_confirmation_code.mock_calls) == 1


@asyncio.coroutine
def test_resend_confirm_view_bad_data(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/resend_confirm', json={
        'not_email': 'hello@bla.com',
    })
    assert req.status == 400
    assert len(mock_cognito.client.resend_confirmation_code.mock_calls) == 0


@asyncio.coroutine
def test_resend_confirm_view_request_timeout(mock_cognito, cloud_client):
    """Test timeout while logging out."""
    mock_cognito.client.resend_confirmation_code.side_effect = \
        asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/resend_confirm', json={
        'email': 'hello@bla.com',
    })
    assert req.status == 502


@asyncio.coroutine
def test_resend_confirm_view_unknown_error(mock_cognito, cloud_client):
    """Test unknown error while logging out."""
    mock_cognito.client.resend_confirmation_code.side_effect = \
        auth_api.UnknownError
    req = yield from cloud_client.post('/api/cloud/resend_confirm', json={
        'email': 'hello@bla.com',
    })
    assert req.status == 502


@asyncio.coroutine
def test_confirm_forgot_password_view(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post(
        '/api/cloud/confirm_forgot_password', json={
            'email': 'hello@bla.com',
            'confirmation_code': '123456',
            'new_password': 'hello2',
        })
    assert req.status == 200
    assert len(mock_cognito.confirm_forgot_password.mock_calls) == 1
    result_code, result_new_password = \
        mock_cognito.confirm_forgot_password.mock_calls[0][1]
    assert result_code == '123456'
    assert result_new_password == 'hello2'


@asyncio.coroutine
def test_confirm_forgot_password_view_bad_data(mock_cognito, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post(
        '/api/cloud/confirm_forgot_password', json={
            'email': 'hello@bla.com',
            'not_confirmation_code': '123456',
            'new_password': 'hello2',
        })
    assert req.status == 400
    assert len(mock_cognito.confirm_forgot_password.mock_calls) == 0


@asyncio.coroutine
def test_confirm_forgot_password_view_request_timeout(mock_cognito,
                                                      cloud_client):
    """Test timeout while logging out."""
    mock_cognito.confirm_forgot_password.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post(
        '/api/cloud/confirm_forgot_password', json={
            'email': 'hello@bla.com',
            'confirmation_code': '123456',
            'new_password': 'hello2',
        })
    assert req.status == 502


@asyncio.coroutine
def test_confirm_forgot_password_view_unknown_error(mock_cognito,
                                                    cloud_client):
    """Test unknown error while logging out."""
    mock_cognito.confirm_forgot_password.side_effect = auth_api.UnknownError
    req = yield from cloud_client.post(
        '/api/cloud/confirm_forgot_password', json={
            'email': 'hello@bla.com',
            'confirmation_code': '123456',
            'new_password': 'hello2',
        })
    assert req.status == 502
