"""Strict connection module."""

import time

from aiohttp.web import Request, StreamResponse

from homeassistant.core import HomeAssistant, callback

from . import TokenScope
from .const import REFRESH_TOKEN_EXPIRATION
from .models import RefreshToken

_COOKIE_NAME = "HASS_STRICT"


@callback
def async_is_valid_token(hass: HomeAssistant, request: Request) -> bool:
    """Check if a request has a valid strict connection token."""
    cookie = request.cookies.get(_COOKIE_NAME)
    return (cookie is not None) and (
        hass.auth.async_validate_access_token(cookie, TokenScope.STRICT_CONNECTION)
        is not None
    )


@callback
def async_delete_cookie(response: StreamResponse) -> None:
    """Delete the strict connection cookie."""
    response.del_cookie(_COOKIE_NAME)


@callback
def async_set_cookie(
    hass: HomeAssistant,
    remote_addr: str | None,
    refresh_token: RefreshToken,
    response: StreamResponse,
) -> None:
    """Set the strict connection cookie.

    Raises InvalidAuthError if the refresh token is invalid.
    """
    access_token = hass.auth.async_create_access_token(
        refresh_token, remote_addr, TokenScope.STRICT_CONNECTION
    )
    if expire_at := refresh_token.expire_at:
        max_age = expire_at - time.time()
    else:
        max_age = REFRESH_TOKEN_EXPIRATION

    response.set_cookie(
        _COOKIE_NAME,
        access_token,
        httponly=True,
        max_age=int(max_age),
        samesite="lax",
        secure=True,
    )
