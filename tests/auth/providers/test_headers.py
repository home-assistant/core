"""Test the Trusted Networks auth provider."""
from ipaddress import ip_address, ip_network

from aiohttp.test_utils import make_mocked_request
import pytest

from homeassistant import auth
from homeassistant.auth import AuthManager
from homeassistant.auth.auth_store import AuthStore
from homeassistant.auth.providers import headers
from homeassistant.components.http import HomeAssistantHTTP
from homeassistant.core import HomeAssistant


@pytest.fixture
def store(hass: HomeAssistant) -> AuthStore:
    """Mock store."""
    return AuthStore(hass)


@pytest.fixture
def provider(hass: HomeAssistant, store: AuthStore) -> headers.HeaderAuthProvider:
    """Mock provider with default config."""
    # This HTTP Object is required because we check the trusted_proxies
    hass.http = HomeAssistantHTTP(
        hass,
        "",
        "",
        "",
        "localhost",
        "8123",
        "",
        True,
        [ip_network("127.0.0.1/32")],
        0,
        False,
        "",
    )
    return headers.HeaderAuthProvider(
        hass, store, headers.CONFIG_SCHEMA({"type": "header"}),
    )


@pytest.fixture
def manager(hass, store, provider):
    """Mock manager."""
    return auth.AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


async def test_login_flow_invalid_network(
    manager: AuthManager, provider: headers.HeaderAuthProvider
):
    """Test login flow from invalid proxy."""
    user = await manager.async_create_user("test-user")

    request = make_mocked_request(
        "GET", "/", headers={"X-Forwarded-Preferred-Username": user.name}
    )

    # not from trusted network
    flow = await provider.async_login_flow(
        {"ip_address": ip_address("127.0.0.2"), "request": request}
    )
    step = await flow.async_step_init()
    assert step["type"] == "abort"
    assert step["reason"] == "not_allowed"


async def test_login_flow_invalid_header(
    manager: AuthManager, provider: headers.HeaderAuthProvider
):
    """Test login flow with an invalid header."""
    await manager.async_create_user("test-user")

    request = make_mocked_request(
        "GET", "/", headers={"X-Forwarded-Preferred-Username": "invalid"}
    )

    flow = await provider.async_login_flow(
        {"ip_address": ip_address("127.0.0.1"), "request": request}
    )
    step = await flow.async_step_init()
    assert step["type"] == "abort"
    assert step["reason"] == "not_allowed"


async def test_login_flow_valid(
    manager: AuthManager, provider: headers.HeaderAuthProvider
):
    """Test login flow."""
    user = await manager.async_create_user("test-user")

    request = make_mocked_request(
        "GET", "/", headers={"X-Forwarded-Preferred-Username": user.name}
    )

    flow = await provider.async_login_flow(
        {"ip_address": ip_address("127.0.0.1"), "request": request}
    )
    step = await flow.async_step_init()
    assert step["type"] == "create_entry"
    assert step["data"]["user"] == user.id
