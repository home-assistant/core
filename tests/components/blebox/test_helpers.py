"""Blebox helpers tests."""

from aiohttp.helpers import BasicAuth

from homeassistant.components.blebox.helpers import get_maybe_authenticated_session
from homeassistant.core import HomeAssistant


async def test_get_maybe_authenticated_session_none(hass: HomeAssistant) -> None:
    """Tests if session auth is None."""
    session = get_maybe_authenticated_session(hass=hass, username="", password="")
    assert session.auth is None


async def test_get_maybe_authenticated_session_auth(hass: HomeAssistant) -> None:
    """Tests if session have BasicAuth."""
    session = get_maybe_authenticated_session(
        hass=hass, username="user", password="password"
    )
    assert isinstance(session.auth, BasicAuth)
