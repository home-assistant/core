"""Tests for the tools to communicate with the cloud."""
import asyncio
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urljoin

import aiohttp
import pytest

from homeassistant.components.cloud import DOMAIN, cloud_api, const
import homeassistant.util.dt as dt_util

from tests.common import mock_coro


MOCK_AUTH = {
    "access_token": "jvCHxpTu2nfORLBRgQY78bIAoK4RPa",
    "expires_at": "2017-08-29T05:33:28.266048+00:00",
    "expires_in": 86400,
    "refresh_token": "C4wR1mgb03cs69EeiFgGOBC8mMQC5Q",
    "scope": "",
    "token_type": "Bearer"
}


def url(path):
    """Create a url."""
    return urljoin(const.SERVERS['development']['host'], path)


@pytest.fixture
def cloud_hass(hass):
    """Fixture to return a hass instance with cloud mode set."""
    hass.data[DOMAIN] = {'mode': 'development'}
    return hass


@pytest.fixture
def mock_write():
    """Mock reading authentication."""
    with patch.object(cloud_api, '_write_auth') as mock:
        yield mock


@pytest.fixture
def mock_read():
    """Mock writing authentication."""
    with patch.object(cloud_api, '_read_auth') as mock:
        yield mock


@asyncio.coroutine
def test_async_login_invalid_auth(cloud_hass, aioclient_mock, mock_write):
    """Test trying to login with invalid credentials."""
    aioclient_mock.post(url('o/token/'), status=401)
    with pytest.raises(cloud_api.Unauthenticated):
        yield from cloud_api.async_login(cloud_hass, 'user', 'pass')

    assert len(mock_write.mock_calls) == 0


@asyncio.coroutine
def test_async_login_cloud_error(cloud_hass, aioclient_mock, mock_write):
    """Test exception in cloud while logging in."""
    aioclient_mock.post(url('o/token/'), status=500)
    with pytest.raises(cloud_api.UnknownError):
        yield from cloud_api.async_login(cloud_hass, 'user', 'pass')

    assert len(mock_write.mock_calls) == 0


@asyncio.coroutine
def test_async_login_client_error(cloud_hass, aioclient_mock, mock_write):
    """Test client error while logging in."""
    aioclient_mock.post(url('o/token/'), exc=aiohttp.ClientError)
    with pytest.raises(cloud_api.UnknownError):
        yield from cloud_api.async_login(cloud_hass, 'user', 'pass')

    assert len(mock_write.mock_calls) == 0


@asyncio.coroutine
def test_async_login(cloud_hass, aioclient_mock, mock_write):
    """Test logging in."""
    aioclient_mock.post(url('o/token/'), json={
        'expires_in': 10
    })
    now = dt_util.utcnow()
    with patch('homeassistant.components.cloud.cloud_api.utcnow',
               return_value=now):
        yield from cloud_api.async_login(cloud_hass, 'user', 'pass')

    assert len(mock_write.mock_calls) == 1
    result_hass, result_data = mock_write.mock_calls[0][1]
    assert result_hass is cloud_hass
    assert result_data == {
        'expires_in': 10,
        'expires_at': (now + timedelta(seconds=10)).isoformat()
    }


@asyncio.coroutine
def test_load_auth_with_no_stored_auth(cloud_hass, mock_read):
    """Test loading authentication with no stored auth."""
    mock_read.return_value = None

    result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None


@asyncio.coroutine
def test_load_auth_timeout_during_verification(cloud_hass, mock_read):
    """Test loading authentication with timeout during verification."""
    mock_read.return_value = MOCK_AUTH

    with patch.object(cloud_api.Cloud, 'async_refresh_account_info',
                      side_effect=asyncio.TimeoutError):
        result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None


@asyncio.coroutine
def test_load_auth_verification_failed_500(cloud_hass, mock_read,
                                           aioclient_mock):
    """Test loading authentication with verify request getting 500."""
    mock_read.return_value = MOCK_AUTH
    aioclient_mock.get(url('account.json'), status=500)

    result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None


@asyncio.coroutine
def test_load_auth_token_refresh_needed_401(cloud_hass, mock_read,
                                            aioclient_mock):
    """Test loading authentication with refresh needed which gets 401."""
    mock_read.return_value = MOCK_AUTH
    aioclient_mock.get(url('account.json'), status=403)
    aioclient_mock.post(url('o/token/'), status=401)

    result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None


@asyncio.coroutine
def test_load_auth_token_refresh_needed_500(cloud_hass, mock_read,
                                            aioclient_mock):
    """Test loading authentication with refresh needed which gets 500."""
    mock_read.return_value = MOCK_AUTH
    aioclient_mock.get(url('account.json'), status=403)
    aioclient_mock.post(url('o/token/'), status=500)

    result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None


@asyncio.coroutine
def test_load_auth_token_refresh_needed_timeout(cloud_hass, mock_read,
                                                aioclient_mock):
    """Test loading authentication with refresh timing out."""
    mock_read.return_value = MOCK_AUTH
    aioclient_mock.get(url('account.json'), status=403)
    aioclient_mock.post(url('o/token/'), exc=asyncio.TimeoutError)

    result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None


@asyncio.coroutine
def test_load_auth_token_refresh_needed_succeeds(cloud_hass, mock_read,
                                                 aioclient_mock):
    """Test loading authentication with refresh timing out."""
    mock_read.return_value = MOCK_AUTH
    aioclient_mock.get(url('account.json'), status=403)

    with patch.object(cloud_api.Cloud, 'async_refresh_access_token',
                      return_value=mock_coro(True)) as mock_refresh:
        result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is None
    assert len(mock_refresh.mock_calls) == 1


@asyncio.coroutine
def test_load_auth_token(cloud_hass, mock_read, aioclient_mock):
    """Test loading authentication with refresh timing out."""
    mock_read.return_value = MOCK_AUTH
    aioclient_mock.get(url('account.json'), json={
        'first_name': 'Paulus',
        'last_name': 'Schoutsen'
    })

    result = yield from cloud_api.async_load_auth(cloud_hass)

    assert result is not None
    assert result.account == {
        'first_name': 'Paulus',
        'last_name': 'Schoutsen'
    }
    assert result.auth == MOCK_AUTH


def test_cloud_properties():
    """Test Cloud class properties."""
    cloud = cloud_api.Cloud(None, MOCK_AUTH)
    assert cloud.access_token == MOCK_AUTH['access_token']
    assert cloud.refresh_token == MOCK_AUTH['refresh_token']


@asyncio.coroutine
def test_cloud_refresh_account_info(cloud_hass, aioclient_mock):
    """Test refreshing account info."""
    aioclient_mock.get(url('account.json'), json={
        'first_name': 'Paulus',
        'last_name': 'Schoutsen'
    })
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    assert cloud.account is None
    result = yield from cloud.async_refresh_account_info()
    assert result
    assert cloud.account == {
        'first_name': 'Paulus',
        'last_name': 'Schoutsen'
    }


@asyncio.coroutine
def test_cloud_refresh_account_info_500(cloud_hass, aioclient_mock):
    """Test refreshing account info and getting 500."""
    aioclient_mock.get(url('account.json'), status=500)
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    assert cloud.account is None
    result = yield from cloud.async_refresh_account_info()
    assert not result
    assert cloud.account is None


@asyncio.coroutine
def test_cloud_refresh_token(cloud_hass, aioclient_mock, mock_write):
    """Test refreshing access token."""
    aioclient_mock.post(url('o/token/'), json={
        'access_token': 'refreshed',
        'expires_in': 10
    })
    now = dt_util.utcnow()
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    with patch('homeassistant.components.cloud.cloud_api.utcnow',
               return_value=now):
        result = yield from cloud.async_refresh_access_token()
    assert result
    assert cloud.auth == {
        'access_token': 'refreshed',
        'expires_in': 10,
        'expires_at': (now + timedelta(seconds=10)).isoformat()
    }
    assert len(mock_write.mock_calls) == 1
    write_hass, write_data = mock_write.mock_calls[0][1]
    assert write_hass is cloud_hass
    assert write_data == cloud.auth


@asyncio.coroutine
def test_cloud_refresh_token_unknown_error(cloud_hass, aioclient_mock,
                                           mock_write):
    """Test refreshing access token."""
    aioclient_mock.post(url('o/token/'), status=500)
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    result = yield from cloud.async_refresh_access_token()
    assert not result
    assert cloud.auth == MOCK_AUTH
    assert len(mock_write.mock_calls) == 0


@asyncio.coroutine
def test_cloud_revoke_token(cloud_hass, aioclient_mock, mock_write):
    """Test revoking access token."""
    aioclient_mock.post(url('o/revoke_token/'))
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    yield from cloud.async_revoke_access_token()
    assert cloud.auth is None
    assert len(mock_write.mock_calls) == 1
    write_hass, write_data = mock_write.mock_calls[0][1]
    assert write_hass is cloud_hass
    assert write_data is None


@asyncio.coroutine
def test_cloud_revoke_token_invalid_client_creds(cloud_hass, aioclient_mock,
                                                 mock_write):
    """Test revoking access token with invalid client credentials."""
    aioclient_mock.post(url('o/revoke_token/'), status=401)
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    with pytest.raises(cloud_api.UnknownError):
        yield from cloud.async_revoke_access_token()
    assert cloud.auth is not None
    assert len(mock_write.mock_calls) == 0


@asyncio.coroutine
def test_cloud_revoke_token_request_error(cloud_hass, aioclient_mock,
                                          mock_write):
    """Test revoking access token with invalid client credentials."""
    aioclient_mock.post(url('o/revoke_token/'), exc=aiohttp.ClientError)
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    with pytest.raises(cloud_api.UnknownError):
        yield from cloud.async_revoke_access_token()
    assert cloud.auth is not None
    assert len(mock_write.mock_calls) == 0


@asyncio.coroutine
def test_cloud_request(cloud_hass, aioclient_mock):
    """Test making request to the cloud."""
    aioclient_mock.post(url('some_endpoint'), json={'hello': 'world'})
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    request = yield from cloud.async_request('post', 'some_endpoint')
    assert request.status == 200
    data = yield from request.json()
    assert data == {'hello': 'world'}


@asyncio.coroutine
def test_cloud_request_requiring_refresh_fail(cloud_hass, aioclient_mock):
    """Test making request to the cloud."""
    aioclient_mock.post(url('some_endpoint'), status=403)
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    with patch.object(cloud_api.Cloud, 'async_refresh_access_token',
                      return_value=mock_coro(False)) as mock_refresh:
        request = yield from cloud.async_request('post', 'some_endpoint')
    assert request.status == 403
    assert len(mock_refresh.mock_calls) == 1


@asyncio.coroutine
def test_cloud_request_requiring_refresh_success(cloud_hass, aioclient_mock):
    """Test making request to the cloud."""
    aioclient_mock.post(url('some_endpoint'), status=403)
    cloud = cloud_api.Cloud(cloud_hass, MOCK_AUTH)
    with patch.object(cloud_api.Cloud, 'async_refresh_access_token',
                      return_value=mock_coro(True)) as mock_refresh, \
            patch.object(cloud_api.Cloud, 'async_refresh_account_info',
                         return_value=mock_coro()) as mock_account_info:
        request = yield from cloud.async_request('post', 'some_endpoint')
    assert request.status == 403
    assert len(mock_refresh.mock_calls) == 1
    assert len(mock_account_info.mock_calls) == 1
