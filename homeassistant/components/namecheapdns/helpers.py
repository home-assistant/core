"""Helpers for the Namecheap DynamicDNS integration."""

import logging

from aiohttp import ClientSession

from .const import UPDATE_URL

_LOGGER = logging.getLogger(__name__)


async def update_namecheapdns(
    session: ClientSession, host: str, domain: str, password: str
):
    """Update namecheap DNS entry."""
    params = {"host": host, "domain": domain, "password": password}

    resp = await session.get(UPDATE_URL, params=params)
    xml_string = await resp.text()

    if "<ErrCount>0</ErrCount>" not in xml_string:
        return False

    return True
