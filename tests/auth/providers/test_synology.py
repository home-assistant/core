"""Unit tests for Synology DSM authentication provider."""
from unittest.mock import AsyncMock

import pytest

from homeassistant.auth import AuthManager, auth_store, models as auth_models
from homeassistant.auth.auth_store import AuthStore
from homeassistant.auth.providers import synology
from homeassistant.auth.providers.synology import SynologyAuthProvider
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def mock_synology_api(aioclient_mock: AiohttpClientMocker):
    """Mock all API requests used by tests below."""

    aioclient_mock.get(
        "http://dummy:5000/webapi/entry.cgi",
        params={
            "api": "SYNO.API.Auth",
            "version": "7",
            "method": "login",
            "account": "test-user",
            "passwd": "password",
            "otp_code": "123",
            "format": "sid",
        },
        json={
            "success": True,
        },
    )

    aioclient_mock.get(
        "http://dummy:5000/webapi/entry.cgi",
        params={
            "api": "SYNO.API.Auth",
            "version": "7",
            "method": "login",
            "account": "test-user",
            "passwd": "password",
            "format": "sid",
        },
        json={"success": True, "data": {"account": "test-user"}},
    )

    aioclient_mock.get(
        "http://dummy:5000/webapi/entry.cgi",
        params={
            "api": "SYNO.Core.NormalUser",
            "version": 1,
            "method": "get",
            "_sid": "secure-session",
        },
        json={
            "success": True,
            "data": {"username": "test-user", "fullname": "Test Name"},
        },
    )


@pytest.fixture
def store(hass: HomeAssistant) -> AuthStore:
    """Mock store."""
    return auth_store.AuthStore(hass)


@pytest.fixture
def provider(hass: HomeAssistant, store: AuthStore) -> SynologyAuthProvider:
    """Mock provider."""
    return synology.SynologyAuthProvider(
        hass,
        store,
        {
            "type": "synology",
            "host": "dummy",
            "port": 5000,
            "secure": False,
            "verify_cert": False,
        },
    )


@pytest.fixture
def manager(
    hass: HomeAssistant, store: AuthStore, provider: SynologyAuthProvider
) -> AuthManager:
    """Mock manager."""
    return AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


async def test_create_new_credential(provider: SynologyAuthProvider):
    """Test that we create a new credential."""
    credentials = await provider.async_get_or_create_credentials(
        {
            "account": "test-user",
        }
    )
    assert credentials.is_new is True
    assert credentials.data["account"] == "test-user"


async def test_match_existing_credentials(provider: SynologyAuthProvider):
    """See if we match existing users."""
    existing = auth_models.Credentials(
        id="dummy-user-existing",
        auth_provider_type="synology",
        auth_provider_id=None,
        data={"account": "user-test"},
        is_new=False,
    )
    provider.async_credentials = AsyncMock(return_value=[existing])
    credentials = await provider.async_get_or_create_credentials(
        {"account": "user-test"}
    )
    assert credentials is existing


async def test_login_flow_without_input(provider: SynologyAuthProvider):
    """Test the login flow UI."""

    flow = await provider.async_login_flow(None)
    step = await flow.async_step_init()
    assert step["type"] == "form"
    assert step["step_id"] == "init"
    assert len(step["errors"]) == 0
    schema_keys = list(step["data_schema"].schema)
    assert schema_keys == ["username", "password", "otp_code"]


async def test_login_flow_empty_password(provider: SynologyAuthProvider):
    """Test the login flow with an empty password."""

    flow = await provider.async_login_flow(None)
    step = await flow.async_step_init({"username": "test-user", "password": " "})
    assert step["type"] == "form"
    assert step["step_id"] == "init"
    assert len(step["errors"]) == 1
    assert step["errors"]["password"] == "empty_password"


async def test_login_flow_empty_username(provider: SynologyAuthProvider):
    """Test the login flow with an empty username."""

    flow = await provider.async_login_flow(None)
    step = await flow.async_step_init({"username": " ", "password": "password"})
    assert step["type"] == "form"
    assert step["step_id"] == "init"
    assert len(step["errors"]) == 1
    assert step["errors"]["username"] == "empty_username"


async def test_login_flow_empty_otp(provider: SynologyAuthProvider):
    """Test the login flow with an empty otp code."""

    flow = await provider.async_login_flow(None)
    step = await flow.async_step_init(
        {"username": "test-user", "password": "password", "otp_code": " "}
    )
    assert step["type"] == "create_entry"
    # OTP is optional, so no error should be raised


async def test_create_new_user_with_meta(manager: AuthManager):
    """See if we can create new users from credentials with metadata."""
    credential = auth_models.Credentials(
        id="dummy-id-user-with-meta",
        auth_provider_type="synology",
        auth_provider_id=None,
        data={"account": "user-test", "sid": "secure-session"},
        is_new=True,
    )
    user = await manager.async_get_or_create_user(credential)
    assert user.is_active
    assert user.name == "Test Name"
