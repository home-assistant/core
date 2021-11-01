"""Unit tests for Synology DSM authentication provider."""
import pytest

from homeassistant.auth import AuthManager, auth_store
from homeassistant.auth.providers import synology


@pytest.fixture
def store(hass):
    """Mock store."""
    return auth_store.AuthStore(hass)


@pytest.fixture
def provider(hass, store):
    """Mock provider."""
    return synology.SynologyAuthProvider(
        hass,
        store,
        {
            "type": "synology",
            "host": "localhost",
            "port": 5000,
            "secure": False,
            "verify_cert": False,
        },
    )


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


async def test_create_new_credential(manager, provider):
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {
            "account": "test-user",
        }
    )
    assert credentials.is_new is True
    assert credentials.data["account"] == "test-user"
