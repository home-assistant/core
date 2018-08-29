"""Test the Trusted Networks auth provider."""
from unittest.mock import Mock

import pytest
import voluptuous as vol

from homeassistant import auth
from homeassistant.auth import auth_store
from homeassistant.auth.providers import trusted_networks as tn_auth


@pytest.fixture
def store(hass):
    """Mock store."""
    return auth_store.AuthStore(hass)


@pytest.fixture
def provider(hass, store):
    """Mock provider."""
    return tn_auth.TrustedNetworksAuthProvider(hass, store, {
        'type': 'trusted_networks'
    })


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return auth.AuthManager(hass, store, {
        (provider.type, provider.id): provider
    }, {})


async def test_trusted_networks_credentials(manager, provider):
    """Test trusted_networks credentials related functions."""
    owner = await manager.async_create_user("test-owner")
    tn_owner_cred = await provider.async_get_or_create_credentials({
        'user': owner.id
    })
    assert tn_owner_cred.is_new is False
    assert any(cred.id == tn_owner_cred.id for cred in owner.credentials)

    user = await manager.async_create_user("test-user")
    tn_user_cred = await provider.async_get_or_create_credentials({
        'user': user.id
    })
    assert tn_user_cred.id != tn_owner_cred.id
    assert tn_user_cred.is_new is False
    assert any(cred.id == tn_user_cred.id for cred in user.credentials)

    with pytest.raises(tn_auth.InvalidUserError):
        await provider.async_get_or_create_credentials({
            'user': 'invalid-user'
        })


async def test_validate_access(provider):
    """Test validate access from trusted networks."""
    with pytest.raises(tn_auth.InvalidAuthError):
        provider.async_validate_access('192.168.0.1')

    provider.hass.http = Mock(trusted_networks=['192.168.0.1'])
    provider.async_validate_access('192.168.0.1')

    with pytest.raises(tn_auth.InvalidAuthError):
        provider.async_validate_access('127.0.0.1')


async def test_login_flow(manager, provider):
    """Test login flow."""
    owner = await manager.async_create_user("test-owner")
    user = await manager.async_create_user("test-user")

    # trusted network didn't loaded
    flow = await provider.async_login_flow({'ip_address': '127.0.0.1'})
    step = await flow.async_step_init()
    assert step['type'] == 'abort'
    assert step['reason'] == 'not_whitelisted'

    provider.hass.http = Mock(trusted_networks=['192.168.0.1'])

    # not from trusted network
    flow = await provider.async_login_flow({'ip_address': '127.0.0.1'})
    step = await flow.async_step_init()
    assert step['type'] == 'abort'
    assert step['reason'] == 'not_whitelisted'

    # from trusted network, list users
    flow = await provider.async_login_flow({'ip_address': '192.168.0.1'})
    step = await flow.async_step_init()
    assert step['step_id'] == 'init'

    schema = step['data_schema']
    assert schema({'user': owner.id})
    with pytest.raises(vol.Invalid):
        assert schema({'user': 'invalid-user'})

    # login with valid user
    step = await flow.async_step_init({'user': user.id})
    assert step['type'] == 'create_entry'
    assert step['data']['user'] == user.id
