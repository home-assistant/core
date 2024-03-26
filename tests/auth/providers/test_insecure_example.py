"""Tests for the insecure example auth provider."""

from unittest.mock import AsyncMock
import uuid

import pytest

from homeassistant.auth import AuthManager, auth_store, models as auth_models
from homeassistant.auth.providers import insecure_example


@pytest.fixture
async def store(hass):
    """Mock store."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    return store


@pytest.fixture
def provider(hass, store):
    """Mock provider."""
    return insecure_example.ExampleAuthProvider(
        hass,
        store,
        {
            "type": "insecure_example",
            "users": [
                {
                    "name": "Test Name",
                    "username": "user-test",
                    "password": "password-test",
                },
                {"username": "🎉", "password": "😎"},
            ],
        },
    )


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


async def test_create_new_credential(manager, provider) -> None:
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {"username": "user-test", "password": "password-test"}
    )
    assert credentials.is_new is True

    user = await manager.async_get_or_create_user(credentials)
    assert user.name == "Test Name"
    assert user.is_active


async def test_match_existing_credentials(store, provider) -> None:
    """See if we match existing users."""
    existing = auth_models.Credentials(
        id=uuid.uuid4(),
        auth_provider_type="insecure_example",
        auth_provider_id=None,
        data={"username": "user-test"},
        is_new=False,
    )
    provider.async_credentials = AsyncMock(return_value=[existing])
    credentials = await provider.async_get_or_create_credentials(
        {"username": "user-test", "password": "password-test"}
    )
    assert credentials is existing


async def test_verify_username(provider) -> None:
    """Test we raise if incorrect user specified."""
    with pytest.raises(insecure_example.InvalidAuthError):
        await provider.async_validate_login("non-existing-user", "password-test")


async def test_verify_password(provider) -> None:
    """Test we raise if incorrect user specified."""
    with pytest.raises(insecure_example.InvalidAuthError):
        await provider.async_validate_login("user-test", "incorrect-password")


async def test_utf_8_username_password(provider) -> None:
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {"username": "🎉", "password": "😎"}
    )
    assert credentials.is_new is True
