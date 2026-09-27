"""Helpers for the Namecheap DynamicDNS integration."""

import logging

from aiohttp import ClientSession

from homeassistant.exceptions import HomeAssistantError

from .const import UPDATE_URL

_LOGGER = logging.getLogger(__name__)


async def update_namecheapdns(
    session: ClientSession, host: str, domain: str, password: str
) -> bool:
    """Update namecheap DNS entry."""
    params = {"host": host, "domain": domain, "password": password}

    resp = await session.get(UPDATE_URL, params=params)
    xml_string = await resp.text()

    if "<ErrCount>0</ErrCount>" not in xml_string:
        if "<Err1>Passwords do not match</Err1>" in xml_string:
            raise AuthFailed
        return False

    return True


class AuthFailed(HomeAssistantError):
    """Authentication error."""
