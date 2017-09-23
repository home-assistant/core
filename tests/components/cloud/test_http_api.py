"""Tests for the HTTP API for the cloud component."""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.cloud import DOMAIN, auth_api


@pytest.fixture
def cloud_client(hass, test_client):
    """Fixture that can fetch from the cloud client."""
    hass.loop.run_until_complete(async_setup_component(hass, 'cloud', {
        'cloud': {
            'mode': 'development'
        }
    }))
    return hass.loop.run_until_complete(test_client(hass.http.app))


@pytest.fixture
def mock_auth(cloud_client, hass):
    """Fixture to mock authentication."""
    auth = hass.data[DOMAIN]['auth'] = MagicMock()
    return auth


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
def test_account_view(mock_auth, cloud_client):
    """Test fetching account if no account available."""
    mock_auth.account = MagicMock(email='hello@home-assistant.io')
    req = yield from cloud_client.get('/api/cloud/account')
    assert req.status == 200
    result = yield from req.json()
    assert result == {'email': 'hello@home-assistant.io'}


@asyncio.coroutine
def test_login_view(mock_auth, cloud_client):
    """Test logging in."""
    mock_auth.account = MagicMock(email='hello@home-assistant.io')
    req = yield from cloud_client.post('/api/cloud/login', json={
        'email': 'my_username',
        'password': 'my_password'
    })

    assert req.status == 200
    result = yield from req.json()
    assert result == {'email': 'hello@home-assistant.io'}
    assert len(mock_auth.login.mock_calls) == 1
    result_user, result_pass = mock_auth.login.mock_calls[0][1]
    assert result_user == 'my_username'
    assert result_pass == 'my_password'


@asyncio.coroutine
def test_login_view_invalid_json(mock_auth, cloud_client):
    """Try logging in with invalid JSON."""
    req = yield from cloud_client.post('/api/cloud/login', data='Not JSON')
    assert req.status == 400
    assert len(mock_auth.mock_calls) == 0


@asyncio.coroutine
def test_login_view_invalid_schema(mock_auth, cloud_client):
    """Try logging in with invalid schema."""
    req = yield from cloud_client.post('/api/cloud/login', json={
        'invalid': 'schema'
    })
    assert req.status == 400
    assert len(mock_auth.mock_calls) == 0


@asyncio.coroutine
def test_login_view_request_timeout(mock_auth, cloud_client):
    """Test request timeout while trying to log in."""
    mock_auth.login.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/login', json={
        'email': 'my_username',
        'password': 'my_password'
    })

    assert req.status == 502


@asyncio.coroutine
def test_login_view_invalid_credentials(mock_auth, cloud_client):
    """Test logging in with invalid credentials."""
    mock_auth.login.side_effect = auth_api.Unauthenticated
    req = yield from cloud_client.post('/api/cloud/login', json={
        'email': 'my_username',
        'password': 'my_password'
    })

    assert req.status == 401


@asyncio.coroutine
def test_login_view_unknown_error(mock_auth, cloud_client):
    """Test unknown error while logging in."""
    mock_auth.login.side_effect = auth_api.UnknownError
    req = yield from cloud_client.post('/api/cloud/login', json={
        'email': 'my_username',
        'password': 'my_password'
    })

    assert req.status == 502


@asyncio.coroutine
def test_logout_view(mock_auth, cloud_client):
    """Test logging out."""
    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 200
    data = yield from req.json()
    assert data == {'message': 'ok'}
    assert len(mock_auth.logout.mock_calls) == 1


@asyncio.coroutine
def test_logout_view_request_timeout(mock_auth, cloud_client):
    """Test timeout while logging out."""
    mock_auth.logout.side_effect = asyncio.TimeoutError
    req = yield from cloud_client.post('/api/cloud/logout')
    assert req.status == 502


@asyncio.coroutine
def test_logout_view_unknown_error(mock_auth, cloud_client):
    """Test unknown error while logging out."""
    mock_auth.logout.side_effect = auth_api.UnknownError
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
