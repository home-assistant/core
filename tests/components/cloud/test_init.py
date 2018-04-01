"""Test the cloud component."""
import asyncio
import json
from unittest.mock import patch, MagicMock, mock_open

import pytest

from homeassistant.components import cloud
from homeassistant.util.dt import utcnow

from tests.common import mock_coro


@pytest.fixture
def mock_os():
    """Mock os module."""
    with patch('homeassistant.components.cloud.os') as os:
        os.path.isdir.return_value = True
        yield os


@asyncio.coroutine
def test_constructor_loads_info_from_constant():
    """Test non-dev mode loads info from SERVERS constant."""
    hass = MagicMock(data={})
    with patch.dict(cloud.SERVERS, {
        'beer': {
            'cognito_client_id': 'test-cognito_client_id',
            'user_pool_id': 'test-user_pool_id',
            'region': 'test-region',
            'relayer': 'test-relayer',
            'google_actions_sync_url': 'test-google_actions_sync_url',
        }
    }), patch('homeassistant.components.cloud.Cloud._fetch_jwt_keyset',
              return_value=mock_coro(True)):
        result = yield from cloud.async_setup(hass, {
            'cloud': {cloud.CONF_MODE: 'beer'}
        })
        assert result

    cl = hass.data['cloud']
    assert cl.mode == 'beer'
    assert cl.cognito_client_id == 'test-cognito_client_id'
    assert cl.user_pool_id == 'test-user_pool_id'
    assert cl.region == 'test-region'
    assert cl.relayer == 'test-relayer'
    assert cl.google_actions_sync_url == 'test-google_actions_sync_url'


@asyncio.coroutine
def test_constructor_loads_info_from_config():
    """Test non-dev mode loads info from SERVERS constant."""
    hass = MagicMock(data={})

    with patch('homeassistant.components.cloud.Cloud._fetch_jwt_keyset',
               return_value=mock_coro(True)):
        result = yield from cloud.async_setup(hass, {
            'cloud': {
                cloud.CONF_MODE: cloud.MODE_DEV,
                'cognito_client_id': 'test-cognito_client_id',
                'user_pool_id': 'test-user_pool_id',
                'region': 'test-region',
                'relayer': 'test-relayer',
            }
        })
    assert result

    cl = hass.data['cloud']
    assert cl.mode == cloud.MODE_DEV
    assert cl.cognito_client_id == 'test-cognito_client_id'
    assert cl.user_pool_id == 'test-user_pool_id'
    assert cl.region == 'test-region'
    assert cl.relayer == 'test-relayer'


@asyncio.coroutine
def test_initialize_loads_info(mock_os, hass):
    """Test initialize will load info from config file."""
    mock_os.path.isfile.return_value = True
    mopen = mock_open(read_data=json.dumps({
        'id_token': 'test-id-token',
        'access_token': 'test-access-token',
        'refresh_token': 'test-refresh-token',
    }))

    cl = cloud.Cloud(hass, cloud.MODE_DEV, None, None)
    cl.iot = MagicMock()
    cl.iot.connect.return_value = mock_coro()

    with patch('homeassistant.components.cloud.open', mopen, create=True), \
            patch('homeassistant.components.cloud.Cloud._decode_claims'):
        yield from cl.async_start(None)

    assert cl.id_token == 'test-id-token'
    assert cl.access_token == 'test-access-token'
    assert cl.refresh_token == 'test-refresh-token'
    assert len(cl.iot.connect.mock_calls) == 1


@asyncio.coroutine
def test_logout_clears_info(mock_os, hass):
    """Test logging out disconnects and removes info."""
    cl = cloud.Cloud(hass, cloud.MODE_DEV, None, None)
    cl.iot = MagicMock()
    cl.iot.disconnect.return_value = mock_coro()

    yield from cl.logout()

    assert len(cl.iot.disconnect.mock_calls) == 1
    assert cl.id_token is None
    assert cl.access_token is None
    assert cl.refresh_token is None
    assert len(mock_os.remove.mock_calls) == 1


@asyncio.coroutine
def test_write_user_info():
    """Test writing user info works."""
    mopen = mock_open()

    cl = cloud.Cloud(MagicMock(), cloud.MODE_DEV, None, None)
    cl.id_token = 'test-id-token'
    cl.access_token = 'test-access-token'
    cl.refresh_token = 'test-refresh-token'

    with patch('homeassistant.components.cloud.open', mopen, create=True):
        cl.write_user_info()

    handle = mopen()

    assert len(handle.write.mock_calls) == 1
    data = json.loads(handle.write.mock_calls[0][1][0])
    assert data == {
        'access_token': 'test-access-token',
        'id_token': 'test-id-token',
        'refresh_token': 'test-refresh-token',
    }


@asyncio.coroutine
def test_subscription_expired():
    """Test subscription being expired."""
    cl = cloud.Cloud(None, cloud.MODE_DEV, None, None)
    token_val = {
        'custom:sub-exp': '2017-11-13'
    }
    with patch.object(cl, '_decode_claims', return_value=token_val), \
            patch('homeassistant.util.dt.utcnow',
                  return_value=utcnow().replace(year=2018)):
        assert cl.subscription_expired


@asyncio.coroutine
def test_subscription_not_expired():
    """Test subscription not being expired."""
    cl = cloud.Cloud(None, cloud.MODE_DEV, None, None)
    token_val = {
        'custom:sub-exp': '2017-11-13'
    }
    with patch.object(cl, '_decode_claims', return_value=token_val), \
            patch('homeassistant.util.dt.utcnow',
                  return_value=utcnow().replace(year=2017, month=11, day=9)):
        assert not cl.subscription_expired
