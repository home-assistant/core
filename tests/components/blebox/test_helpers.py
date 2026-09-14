"""Blebox helpers tests."""

from aiohttp import encode_basic_auth
from aiohttp.hdrs import AUTHORIZATION

from homeassistant.components.blebox.helpers import get_maybe_authenticated_session
from homeassistant.core import HomeAssistant


async def test_get_maybe_authenticated_session_none(hass: HomeAssistant) -> None:
    """Tests if the session has no authorization header."""
    session = get_maybe_authenticated_session(hass=hass, username="", password="")
    assert AUTHORIZATION not in session.headers


async def test_get_maybe_authenticated_session_auth(hass: HomeAssistant) -> None:
    """Tests if the session has a basic authorization header."""
    session = get_maybe_authenticated_session(
        hass=hass, username="user", password="password"
    )
    assert session.headers[AUTHORIZATION] == encode_basic_auth("user", "password")
