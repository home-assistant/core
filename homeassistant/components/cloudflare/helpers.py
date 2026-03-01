"""Helpers for the Cloudflare integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
import pycfdns

_LOGGER = logging.getLogger(__name__)


def get_zone_id(target_zone_name: str, zones: list[pycfdns.ZoneModel]) -> str | None:
    """Get the zone ID for the target zone name."""
    for zone in zones:
        if zone["name"] == target_zone_name:
            return zone["id"]
    return None


async def async_create_a_record(
    session: ClientSession,
    api_token: str,
    zone_id: str,
    name: str,
    content: str,
    proxied: bool,
) -> dict[str, Any] | None:
    """Create an A record if it does not exist.

    Returns the created record dict or None if failed.
    """
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    payload = {
        "type": "A",
        "name": name,
        "content": content,
        "ttl": 1,
        "proxied": proxied,
    }
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            _LOGGER.warning(
                "Failed creating record %s (%s): %s",
                name,
                resp.status,
                await resp.text(),
            )
            return None
        data = await resp.json()
        if not data.get("success"):
            _LOGGER.warning("Cloudflare API error creating record %s: %s", name, data)
            return None
        return data.get("result")


async def async_update_proxied_state(
    session: ClientSession,
    api_token: str,
    zone_id: str,
    record_id: str,
    name: str,
    content: str,
    proxied: bool,
    ttl: int | None = None,
) -> bool:
    """Update only the proxied state of an existing record."""
    url = (
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    )
    payload: dict[str, Any] = {
        "type": "A",
        "name": name,
        "content": content,
        "proxied": proxied,
    }
    if ttl is not None:
        payload["ttl"] = ttl
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    async with session.put(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            _LOGGER.warning(
                "Failed updating proxied state for %s (%s): %s",
                name,
                resp.status,
                await resp.text(),
            )
            return False
        data = await resp.json()
        if not data.get("success"):
            _LOGGER.warning(
                "Cloudflare API error updating proxied state %s: %s", name, data
            )
            return False
        return True
