"""Tests for the legacy_api_password auth provider."""
from unittest.mock import Mock

import pytest

from homeassistant import auth
from homeassistant.auth import auth_store
from homeassistant.auth.providers import legacy_api_password


@pytest.fixture
def store(hass):
    """Mock store."""
    return auth_store.AuthStore(hass)


@pytest.fixture
def provider(hass, store):
    """Mock provider."""
    return legacy_api_password.LegacyApiPasswordAuthProvider(hass, store, {
        'type': 'legacy_api_password',
    })


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return auth.AuthManager(hass, store, {
        (provider.type, provider.id): provider
    })


async def test_create_new_credential(manager, provider):
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials({})
    assert credentials.data["username"] is legacy_api_password.LEGACY_USER
    assert credentials.is_new is True

    user = await manager.async_get_or_create_user(credentials)
    assert user.name == legacy_api_password.LEGACY_USER
    assert user.is_active


async def test_only_one_credentials(manager, provider):
    """Call create twice will return same credential."""
    credentials = await provider.async_get_or_create_credentials({})
    await manager.async_get_or_create_user(credentials)
    credentials2 = await provider.async_get_or_create_credentials({})
    assert credentials2.data["username"] == legacy_api_password.LEGACY_USER
    assert credentials2.id == credentials.id
    assert credentials2.is_new is False


async def test_verify_not_load(hass, provider):
    """Test we raise if http module not load."""
    with pytest.raises(ValueError):
        provider.async_validate_login('test-password')
    hass.http = Mock(api_password=None)
    with pytest.raises(ValueError):
        provider.async_validate_login('test-password')
    hass.http = Mock(api_password='test-password')
    provider.async_validate_login('test-password')


async def test_verify_login(hass, provider):
    """Test we raise if http module not load."""
    hass.http = Mock(api_password='test-password')
    provider.async_validate_login('test-password')
    hass.http = Mock(api_password='test-password')
    with pytest.raises(legacy_api_password.InvalidAuthError):
        provider.async_validate_login('invalid-password')


async def test_utf_8_username_password(provider):
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials({
        'username': '🎉',
        'password': '😎',
    })
    assert credentials.is_new is True
