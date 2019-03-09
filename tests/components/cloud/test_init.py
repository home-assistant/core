"""Test the cloud component."""
import asyncio
import json
from unittest.mock import patch, MagicMock, mock_open

import pytest

from homeassistant.setup import async_setup_component
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
            'subscription_info_url': 'test-subscription-info-url',
            'cloudhook_create_url': 'test-cloudhook_create_url',
        }
    }):
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
    assert cl.subscription_info_url == 'test-subscription-info-url'
    assert cl.cloudhook_create_url == 'test-cloudhook_create_url'


@asyncio.coroutine
def test_constructor_loads_info_from_config():
    """Test non-dev mode loads info from SERVERS constant."""
    hass = MagicMock(data={})

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


async def test_initialize_loads_info(mock_os, hass):
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
        await cl.async_start(None)

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
def test_subscription_expired(hass):
    """Test subscription being expired after 3 days of expiration."""
    cl = cloud.Cloud(hass, cloud.MODE_DEV, None, None)
    token_val = {
        'custom:sub-exp': '2017-11-13'
    }
    with patch.object(cl, '_decode_claims', return_value=token_val), \
            patch('homeassistant.util.dt.utcnow',
                  return_value=utcnow().replace(year=2017, month=11, day=13)):
        assert not cl.subscription_expired

    with patch.object(cl, '_decode_claims', return_value=token_val), \
            patch('homeassistant.util.dt.utcnow',
                  return_value=utcnow().replace(
                      year=2017, month=11, day=19, hour=23, minute=59,
                      second=59)):
        assert not cl.subscription_expired

    with patch.object(cl, '_decode_claims', return_value=token_val), \
            patch('homeassistant.util.dt.utcnow',
                  return_value=utcnow().replace(
                      year=2017, month=11, day=20, hour=0, minute=0,
                      second=0)):
        assert cl.subscription_expired


@asyncio.coroutine
def test_subscription_not_expired(hass):
    """Test subscription not being expired."""
    cl = cloud.Cloud(hass, cloud.MODE_DEV, None, None)
    token_val = {
        'custom:sub-exp': '2017-11-13'
    }
    with patch.object(cl, '_decode_claims', return_value=token_val), \
            patch('homeassistant.util.dt.utcnow',
                  return_value=utcnow().replace(year=2017, month=11, day=9)):
        assert not cl.subscription_expired


async def test_create_cloudhook_no_login(hass):
    """Test create cloudhook when not logged in."""
    assert await async_setup_component(hass, 'cloud', {})
    coro = mock_coro({'yo': 'hey'})
    with patch('homeassistant.components.cloud.cloudhooks.'
               'Cloudhooks.async_create', return_value=coro) as mock_create, \
            pytest.raises(cloud.CloudNotAvailable):
        await hass.components.cloud.async_create_cloudhook('hello')

    assert len(mock_create.mock_calls) == 0


async def test_delete_cloudhook_no_setup(hass):
    """Test delete cloudhook when not logged in."""
    coro = mock_coro()
    with patch('homeassistant.components.cloud.cloudhooks.'
               'Cloudhooks.async_delete', return_value=coro) as mock_delete, \
            pytest.raises(cloud.CloudNotAvailable):
        await hass.components.cloud.async_delete_cloudhook('hello')

    assert len(mock_delete.mock_calls) == 0


async def test_create_cloudhook(hass):
    """Test create cloudhook."""
    assert await async_setup_component(hass, 'cloud', {})
    coro = mock_coro({'cloudhook_url': 'hello'})
    with patch('homeassistant.components.cloud.cloudhooks.'
               'Cloudhooks.async_create', return_value=coro) as mock_create, \
            patch('homeassistant.components.cloud.async_is_logged_in',
                  return_value=True):
        result = await hass.components.cloud.async_create_cloudhook('hello')

    assert result == 'hello'
    assert len(mock_create.mock_calls) == 1


async def test_delete_cloudhook(hass):
    """Test delete cloudhook."""
    assert await async_setup_component(hass, 'cloud', {})
    coro = mock_coro()
    with patch('homeassistant.components.cloud.cloudhooks.'
               'Cloudhooks.async_delete', return_value=coro) as mock_delete, \
            patch('homeassistant.components.cloud.async_is_logged_in',
                  return_value=True):
        await hass.components.cloud.async_delete_cloudhook('hello')

    assert len(mock_delete.mock_calls) == 1


async def test_async_logged_in(hass):
    """Test if is_logged_in works."""
    # Cloud not loaded
    assert hass.components.cloud.async_is_logged_in() is False

    assert await async_setup_component(hass, 'cloud', {})

    # Cloud loaded, not logged in
    assert hass.components.cloud.async_is_logged_in() is False

    hass.data['cloud'].id_token = "some token"

    # Cloud loaded, logged in
    assert hass.components.cloud.async_is_logged_in() is True


async def test_async_active_subscription(hass):
    """Test if is_logged_in works."""
    # Cloud not loaded
    assert hass.components.cloud.async_active_subscription() is False

    assert await async_setup_component(hass, 'cloud', {})

    # Cloud loaded, not logged in
    assert hass.components.cloud.async_active_subscription() is False

    hass.data['cloud'].id_token = "some token"

    # Cloud loaded, logged in, invalid sub
    with patch('jose.jwt.get_unverified_claims', return_value={
            'custom:sub-exp': '{}-12-31'.format(utcnow().year - 1)
    }):
        assert hass.components.cloud.async_active_subscription() is False

    # Cloud loaded, logged in, valid sub
    with patch('jose.jwt.get_unverified_claims', return_value={
            'custom:sub-exp': '{}-01-01'.format(utcnow().year + 1)
    }):
        assert hass.components.cloud.async_active_subscription() is True
