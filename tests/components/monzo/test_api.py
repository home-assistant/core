"""Tests for the Monzo API."""

from homeassistant.components.monzo.api import MonzoAPI
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def test_access_token(hass: HomeAssistant) -> None:
    """Test returning a static access token."""
    api = MonzoAPI(async_get_clientsession(hass), "access-token")

    assert await api.async_get_access_token() == "access-token"
