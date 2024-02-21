"""Strict connection module."""

import time

from aiohttp.web import Request, StreamResponse

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import is_cloud_connection

from . import TokenScope
from .const import REFRESH_TOKEN_EXPIRATION
from .models import RefreshToken

_COOKIE_NAME = "HASS-SC"
PREFIXED_COOKIE_NAME = f"__Host-{_COOKIE_NAME}"


def _get_cookie_name(is_cloud: bool) -> str:
    """Return the cookie name."""
    return PREFIXED_COOKIE_NAME if is_cloud else _COOKIE_NAME


@callback
def async_is_valid_token(hass: HomeAssistant, request: Request) -> bool:
    """Check if a request has a valid strict connection token."""
    cookie = request.cookies.get(_get_cookie_name(is_cloud_connection(hass)))
    return (cookie is not None) and (
        hass.auth.async_validate_access_token(cookie, TokenScope.STRICT_CONNECTION)
        is not None
    )


@callback
def async_delete_cookie(hass: HomeAssistant, response: StreamResponse) -> None:
    """Delete the strict connection cookie."""
    response.del_cookie(_get_cookie_name(is_cloud_connection(hass)))


@callback
def async_set_cookie(
    hass: HomeAssistant,
    request: Request,
    refresh_token: RefreshToken,
    response: StreamResponse,
) -> None:
    """Set the strict connection cookie.

    Raises InvalidAuthError if the refresh token is invalid.
    """
    access_token = hass.auth.async_create_access_token(
        refresh_token, request.remote, TokenScope.STRICT_CONNECTION
    )
    if expire_at := refresh_token.expire_at:
        max_age = expire_at - time.time()
    else:
        max_age = REFRESH_TOKEN_EXPIRATION

    is_cloud = is_cloud_connection(hass)

    response.set_cookie(
        _get_cookie_name(is_cloud),
        access_token,
        httponly=True,
        max_age=int(max_age),
        samesite="lax",
        secure=is_cloud or request.secure,
    )
