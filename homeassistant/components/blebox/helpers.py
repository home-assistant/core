"""Blebox helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp

from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)


def get_maybe_authenticated_session(hass, password, username):
    """Return proper session object."""
    if username and password:
        auth = aiohttp.BasicAuth(login=username, password=password)
        return async_create_clientsession(hass, auth=auth)

    return async_get_clientsession(hass)


def get_non_empty_key(dictionary: Mapping[str, Any], key: str) -> str | None:
    """Return None if key's value is empty string."""
    if value := dictionary.get(key):
       return value
    return None
