"""Test the yolink authentication managers."""

from homeassistant.components.yolink.api import StaticTokenAuth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def test_static_token_auth(hass: HomeAssistant) -> None:
    """Test the authentication manager for an already resolved token."""
    auth = StaticTokenAuth(async_get_clientsession(hass), "mock-access-token")

    assert auth.access_token() == "mock-access-token"
    assert await auth.check_and_refresh_token() == "mock-access-token"
    assert auth.http_auth_header() == "Bearer mock-access-token"
