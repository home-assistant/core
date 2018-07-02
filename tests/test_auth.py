"""Tests for the Home Assistant auth module."""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from homeassistant import auth, data_entry_flow
from homeassistant.util import dt as dt_util
from tests.common import MockUser, ensure_auth_manager_loaded, flush_store


@pytest.fixture
def mock_hass(loop):
    """Hass mock with minimum amount of data set to make it work with auth."""
    hass = Mock()
    hass.config.skip_pip = True
    return hass


async def test_auth_manager_from_config_validates_config_and_id(mock_hass):
    """Test get auth providers."""
    manager = await auth.auth_manager_from_config(mock_hass, [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'users': [],
    }, {
        'name': 'Invalid config because no users',
        'type': 'insecure_example',
        'id': 'invalid_config',
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
        'users': [],
    }, {
        'name': 'Wrong because duplicate ID',
        'type': 'insecure_example',
        'id': 'another',
        'users': [],
    }])

    providers = [{
            'name': provider.name,
            'id': provider.id,
            'type': provider.type,
        } for provider in manager.async_auth_providers]
    assert providers == [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'id': None,
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
    }]


async def test_create_new_user(hass, hass_storage):
    """Test creating new user."""
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }])

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    credentials = step['result']
    user = await manager.async_get_or_create_user(credentials)
    assert user is not None
    assert user.is_owner is True
    assert user.name == 'Test Name'


async def test_login_as_existing_user(mock_hass):
    """Test login as existing user."""
    manager = await auth.auth_manager_from_config(mock_hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }])
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    user.credentials.append(auth.Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'},
        is_new=False,
    ))

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    credentials = step['result']

    user = await manager.async_get_or_create_user(credentials)
    assert user is not None
    assert user.id == 'mock-user'
    assert user.is_owner is False
    assert user.is_active is False
    assert user.name == 'Paulus'


async def test_linking_user_to_two_auth_providers(hass, hass_storage):
    """Test linking user to two auth providers."""
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
        }]
    }, {
        'type': 'insecure_example',
        'id': 'another-provider',
        'users': [{
            'username': 'another-user',
            'password': 'another-password',
        }]
    }])

    step = await manager.login_flow.async_init(('insecure_example', None))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    user = await manager.async_get_or_create_user(step['result'])
    assert user is not None

    step = await manager.login_flow.async_init(('insecure_example',
                                                'another-provider'))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'another-user',
        'password': 'another-password',
    })
    await manager.async_link_user(user, step['result'])
    assert len(user.credentials) == 2


async def test_saving_loading(hass, hass_storage):
    """Test storing and saving data.

    Creates one of each type that we store to test we restore correctly.
    """
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
        }]
    }])

    step = await manager.login_flow.async_init(('insecure_example', None))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    user = await manager.async_get_or_create_user(step['result'])

    client = await manager.async_create_client(
        'test', redirect_uris=['https://example.com'])

    refresh_token = await manager.async_create_refresh_token(user, client.id)

    manager.async_create_access_token(refresh_token)

    await flush_store(manager._store._store)

    store2 = auth.AuthStore(hass)
    users = await store2.async_get_users()
    assert len(users) == 1
    assert users[0] == user

    clients = await store2.async_get_clients()
    assert len(clients) == 1
    assert clients[0] == client


def test_access_token_expired():
    """Test that the expired property on access tokens work."""
    refresh_token = auth.RefreshToken(
        user=None,
        client_id='bla'
    )

    access_token = auth.AccessToken(
        refresh_token=refresh_token
    )

    assert access_token.expired is False

    with patch('homeassistant.auth.dt_util.utcnow',
               return_value=dt_util.utcnow() + auth.ACCESS_TOKEN_EXPIRATION):
        assert access_token.expired is True

    almost_exp = dt_util.utcnow() + auth.ACCESS_TOKEN_EXPIRATION - timedelta(1)
    with patch('homeassistant.auth.dt_util.utcnow', return_value=almost_exp):
        assert access_token.expired is False


async def test_cannot_retrieve_expired_access_token(hass):
    """Test that we cannot retrieve expired access tokens."""
    manager = await auth.auth_manager_from_config(hass, [])
    client = await manager.async_create_client('test')
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, client.id)
    assert refresh_token.user.id is user.id
    assert refresh_token.client_id is client.id

    access_token = manager.async_create_access_token(refresh_token)
    assert manager.async_get_access_token(access_token.token) is access_token

    with patch('homeassistant.auth.dt_util.utcnow',
               return_value=dt_util.utcnow() + auth.ACCESS_TOKEN_EXPIRATION):
        assert manager.async_get_access_token(access_token.token) is None

    # Even with unpatched time, it should have been removed from manager
    assert manager.async_get_access_token(access_token.token) is None


async def test_get_or_create_client(hass):
    """Test that get_or_create_client works."""
    manager = await auth.auth_manager_from_config(hass, [])

    client1 = await manager.async_get_or_create_client(
        'Test Client', redirect_uris=['https://test.com/1'])
    assert client1.name is 'Test Client'

    client2 = await manager.async_get_or_create_client(
        'Test Client', redirect_uris=['https://test.com/1'])
    assert client2.id is client1.id


async def test_cannot_create_refresh_token_with_invalide_client_id(hass):
    """Test that we cannot create refresh token with invalid client id."""
    manager = await auth.auth_manager_from_config(hass, [])
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(user, 'bla')


async def test_cannot_create_refresh_token_with_invalide_user(hass):
    """Test that we cannot create refresh token with invalid client id."""
    manager = await auth.auth_manager_from_config(hass, [])
    client = await manager.async_create_client('test')
    user = MockUser(id='invalid-user')
    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(user, client.id)
