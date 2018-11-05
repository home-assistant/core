"""Tests for the insecure example auth provider."""
from unittest.mock import Mock
import uuid

import pytest

from homeassistant.auth import auth_store, models as auth_models, AuthManager
from homeassistant.auth.providers import insecure_example

from tests.common import mock_coro


@pytest.fixture
def store(hass):
    """Mock store."""
    return auth_store.AuthStore(hass)


@pytest.fixture
def provider(hass, store):
    """Mock provider."""
    return insecure_example.ExampleAuthProvider(hass, store, {
        'type': 'insecure_example',
        'users': [
            {
                'name': 'Test Name',
                'username': 'user-test',
                'password': 'password-test',
            },
            {
                'username': '🎉',
                'password': '😎',
            }
        ]
    })


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return AuthManager(hass, store, {
        (provider.type, provider.id): provider
    }, {})


async def test_create_new_credential(manager, provider):
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials({
        'username': 'user-test',
        'password': 'password-test',
    })
    assert credentials.is_new is True

    user = await manager.async_get_or_create_user(credentials)
    assert user.name == 'Test Name'
    assert user.is_active


async def test_match_existing_credentials(store, provider):
    """See if we match existing users."""
    existing = auth_models.Credentials(
        id=uuid.uuid4(),
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={
            'username': 'user-test'
        },
        is_new=False,
    )
    provider.async_credentials = Mock(return_value=mock_coro([existing]))
    credentials = await provider.async_get_or_create_credentials({
        'username': 'user-test',
        'password': 'password-test',
    })
    assert credentials is existing


async def test_verify_username(provider):
    """Test we raise if incorrect user specified."""
    with pytest.raises(insecure_example.InvalidAuthError):
        await provider.async_validate_login(
            'non-existing-user', 'password-test')


async def test_verify_password(provider):
    """Test we raise if incorrect user specified."""
    with pytest.raises(insecure_example.InvalidAuthError):
        await provider.async_validate_login(
            'user-test', 'incorrect-password')


async def test_utf_8_username_password(provider):
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials({
        'username': '🎉',
        'password': '😎',
    })
    assert credentials.is_new is True
