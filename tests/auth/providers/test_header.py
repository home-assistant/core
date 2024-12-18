"""Test the Trusted Networks auth provider."""

from ipaddress import ip_address
from unittest.mock import Mock, patch

from hass_nabucasa import remote
import pytest
import voluptuous as vol

from homeassistant import auth
from homeassistant.auth import auth_store
from homeassistant.auth.models import RefreshFlowContext
from homeassistant.auth.providers import header as header_auth
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
async def store(hass: HomeAssistant) -> auth_store.AuthStore:
    """Mock store."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    return store


@pytest.fixture
def provider(
    hass: HomeAssistant, store: auth_store.AuthStore
) -> header_auth.HeaderAuthProvider:
    """Mock provider."""
    return header_auth.HeaderAuthProvider(
        hass,
        store,
        header_auth.CONFIG_SCHEMA(
            {
                "type": "header",
                "token_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            },
        ),
    )


@pytest.fixture
def provider_bypass_login(
    hass: HomeAssistant, store: auth_store.AuthStore
) -> header_auth.HeaderAuthProvider:
    """Mock provider."""
    return header_auth.HeaderAuthProvider(
        hass,
        store,
        header_auth.CONFIG_SCHEMA(
            {
                "type": "header",
                "token_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                "allow_bypass_login": True,
            },
        ),
    )


@pytest.fixture
def manager(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    provider: header_auth.HeaderAuthProvider,
) -> auth.AuthManager:
    """Mock manager."""
    return auth.AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


@pytest.fixture
def manager_bypass_login(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    provider_bypass_login: header_auth.HeaderAuthProvider,
) -> auth.AuthManager:
    """Mock manager with allow bypass login."""
    return auth.AuthManager(
        hass,
        store,
        {(provider_bypass_login.type, provider_bypass_login.id): provider_bypass_login},
        {},
    )


async def test_config_schema() -> None:
    """Test CONFIG_SCHEMA."""
    # Valid configuration
    header_auth.CONFIG_SCHEMA(
        {
            "type": "header",
            "token_sha256": "abc123",
            "allow_bypass_login": True,
        }
    )
    # Wrong token format
    with pytest.raises(vol.Invalid):
        header_auth.CONFIG_SCHEMA(
            {
                "type": "trusted_networks",
                "token_sha256": "abc123",
                "allow_bypass_login": "hi",
            }
        )


async def test_trusted_networks_credentials(
    manager: auth.AuthManager, provider: header_auth.HeaderAuthProvider
) -> None:
    """Test header credentials related functions."""
    owner = await manager.async_create_user("test-owner")
    tn_owner_cred = await provider.async_get_or_create_credentials({"user": owner.id})
    assert tn_owner_cred.is_new is False
    assert any(cred.id == tn_owner_cred.id for cred in owner.credentials)

    user = await manager.async_create_user("test-user")
    tn_user_cred = await provider.async_get_or_create_credentials({"user": user.id})
    assert tn_user_cred.id != tn_owner_cred.id
    assert tn_user_cred.is_new is False
    assert any(cred.id == tn_user_cred.id for cred in user.credentials)

    with pytest.raises(header_auth.InvalidUserError):
        await provider.async_get_or_create_credentials({"user": "invalid-user"})


async def test_validate_access(provider: header_auth.HeaderAuthProvider) -> None:
    """Test validate access from trusted networks."""
    provider.async_validate_access("test")

    with pytest.raises(auth.InvalidAuthError):
        provider.async_validate_access("not test")


async def test_validate_access_cloud(
    hass: HomeAssistant,
    provider: header_auth.HeaderAuthProvider,
) -> None:
    """Test validate access from trusted networks are blocked from cloud."""
    hass.config.components.add("cloud")

    provider.async_validate_access("test")

    remote.is_cloud_request.set(True)
    with pytest.raises(auth.InvalidAuthError):
        provider.async_validate_access("test")


async def test_validate_refresh_token(
    provider: header_auth.HeaderAuthProvider,
) -> None:
    """Verify re-validation of refresh token."""
    with patch.object(provider, "async_validate_access") as mock:
        with pytest.raises(auth.InvalidAuthError):
            provider.async_validate_refresh_token(Mock(), RefreshFlowContext())

        provider.async_validate_refresh_token(
            Mock(), RefreshFlowContext(headers={header_auth.HEADER_NAME: "test"})
        )
        mock.assert_called_once_with("test")


async def test_login_flow(
    manager: auth.AuthManager, provider: header_auth.HeaderAuthProvider
) -> None:
    """Test login flow."""
    owner = await manager.async_create_user("test-owner")
    user = await manager.async_create_user("test-user")

    # missing header
    flow = await provider.async_login_flow(
        {"headers": {}, "ip_address": ip_address("127.0.0.1")}
    )
    step = await flow.async_step_init()
    assert step["type"] == FlowResultType.ABORT
    assert step["reason"] == "not_allowed"

    # header present, list users
    flow = await provider.async_login_flow(
        {
            "headers": {header_auth.HEADER_NAME: "test"},
            "ip_address": ip_address("127.0.0.1"),
        }
    )
    step = await flow.async_step_init()
    assert step["step_id"] == "init"

    schema = step["data_schema"]
    assert schema({"user": owner.id})
    with pytest.raises(vol.Invalid):
        assert schema({"user": "invalid-user"})

    # login with valid user
    step = await flow.async_step_init({"user": user.id})
    assert step["type"] == FlowResultType.CREATE_ENTRY
    assert step["data"]["user"] == user.id


async def test_bypass_login_flow(
    manager_bypass_login: auth.AuthManager,
    provider_bypass_login: header_auth.HeaderAuthProvider,
) -> None:
    """Test login flow can be bypass if only one user available."""
    owner = await manager_bypass_login.async_create_user("test-owner")

    # incorrect header
    flow = await provider_bypass_login.async_login_flow(
        {"headers": {header_auth.HEADER_NAME: "not test"}}
    )
    step = await flow.async_step_init()
    assert step["type"] == FlowResultType.ABORT
    assert step["reason"] == "not_allowed"

    # correct header, only one available user, bypass the login flow
    flow = await provider_bypass_login.async_login_flow(
        {
            "headers": {header_auth.HEADER_NAME: "test"},
            "ip_address": ip_address("127.0.0.1"),
        }
    )
    step = await flow.async_step_init()
    assert step["type"] == FlowResultType.CREATE_ENTRY
    assert step["data"]["user"] == owner.id

    user = await manager_bypass_login.async_create_user("test-user")

    # correct header, two available user, show up login form
    flow = await provider_bypass_login.async_login_flow(
        {
            "headers": {header_auth.HEADER_NAME: "test"},
            "ip_address": ip_address("127.0.0.1"),
        }
    )
    step = await flow.async_step_init()
    schema = step["data_schema"]
    # both owner and user listed
    assert schema({"user": owner.id})
    assert schema({"user": user.id})
