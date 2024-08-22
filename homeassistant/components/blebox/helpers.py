"""Blebox helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp

from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def get_maybe_authenticated_session(
    hass: HomeAssistant, password: str | None, username: str | None
) -> aiohttp.ClientSession:
    """Return proper session object."""
    if username and password:
        auth = aiohttp.BasicAuth(login=username, password=password)
        return async_create_clientsession(hass, auth=auth)

    return async_get_clientsession(hass)
