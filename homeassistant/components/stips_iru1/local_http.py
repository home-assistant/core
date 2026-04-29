"""Local HTTP helpers for DNS-first IRU1 control."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import re
import time
from typing import Any

import aiohttp
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_HOST_CACHE_TTL_SECONDS = 60.0


@dataclass(slots=True)
class _HostCacheEntry:
    hosts: list[str]
    live_ip: str
    expires_at: float


_HOST_CACHE: dict[tuple[str, str], _HostCacheEntry] = {}


def _local_http_auth() -> aiohttp.BasicAuth | None:
    """Build optional auth for local endpoint calls.

    LAN auth credentials are device/user-specific and must not be hardcoded in core.
    """
    return None


def _dedupe_hosts(hosts: list[str]) -> list[str]:
    out: list[str] = []
    for host in hosts:
        h = str(host or "").strip()
        if h and h not in out:
            out.append(h)
    return out


def _is_valid_catalog_hostname(value: str) -> bool:
    """Validate cloud-provided host name to avoid SSRF primitives."""
    s = value.strip().lower()
    if not s or len(s) > 253:
        return False
    if any(ch.isspace() for ch in s):
        return False
    if any(ch in s for ch in (":", "/", "@", "?", "#", "%", "\\")):
        return False
    try:
        ipaddress.ip_address(s)
    except ValueError:
        pass
    else:
        return False
    labels = s.split(".")
    if any(not label for label in labels):
        return False
    return all(_HOST_LABEL_RE.fullmatch(label) for label in labels)


def iter_dns_host_candidates(
    device_unique_name: str, backend_ip: str = ""
) -> list[str]:
    """Build DNS-first host candidates with backend IP as a last resort."""
    hosts: list[str] = []
    unique_name = str(device_unique_name or "").strip().lower()
    if _is_valid_catalog_hostname(unique_name):
        hosts.append(unique_name)
        if "." not in unique_name:
            hosts.append(f"{unique_name}.local")

    ip_s = str(backend_ip or "").strip()
    if ip_s:
        try:
            ipaddress.ip_address(ip_s)
            hosts.append(ip_s)
        except ValueError:
            # Keep malformed/non-IP values out of host candidates.
            pass
    return _dedupe_hosts(hosts)


def _extract_live_ip(payload: dict[str, Any]) -> str:
    for key in ("ip_address", "ipAddress", "ip", "Ip"):
        val = payload.get(key)
        if val is None:
            continue
        s = str(val).strip()
        if not s:
            continue
        try:
            ipaddress.ip_address(s)
        except ValueError:
            continue
        else:
            return s
    return ""


async def async_fetch_device_info_live_ip(
    hass: HomeAssistant,
    *,
    host: str,
    timeout: aiohttp.ClientTimeout,
) -> str:
    """Try GET /device_info on one host and return a validated IP when available."""
    session = async_get_clientsession(hass)
    auth = _local_http_auth()
    url = str(URL.build(scheme="http", host=host, path="/device_info"))
    try:
        async with session.get(url, auth=auth, timeout=timeout) as response:
            if response.status >= 400:
                return ""
            try:
                payload = await response.json(content_type=None)
            except aiohttp.ContentTypeError:
                body = await response.text()
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    return ""
            except ValueError:
                body = await response.text()
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    return ""
            if not isinstance(payload, dict):
                return ""
            return _extract_live_ip(payload)
    except TimeoutError:
        return ""
    except aiohttp.ClientError:
        return ""


async def async_build_control_hosts(
    hass: HomeAssistant,
    *,
    device_unique_name: str,
    backend_ip: str,
) -> tuple[list[str], str]:
    """Resolve command host list and live IP using DNS first, backend IP last.

    Returns (hosts, live_ip). live_ip is empty when unavailable.
    """
    cache_key = (
        str(device_unique_name or "").strip().lower(),
        str(backend_ip or "").strip(),
    )
    now = time.monotonic()
    cache_entry = _HOST_CACHE.get(cache_key)
    if cache_entry is not None and cache_entry.expires_at > now:
        return list(cache_entry.hosts), cache_entry.live_ip

    hosts = iter_dns_host_candidates(device_unique_name, backend_ip)
    if not hosts:
        return [], ""

    probe_timeout = aiohttp.ClientTimeout(
        total=2, connect=1, sock_connect=1, sock_read=1.5
    )
    live_ip = ""
    for host in hosts:
        ip = await async_fetch_device_info_live_ip(
            hass, host=host, timeout=probe_timeout
        )
        if ip:
            live_ip = ip
            break

    if live_ip and live_ip not in hosts:
        # Keep DNS hosts first as requested; add discovered IP as fallback.
        hosts.append(live_ip)
    deduped_hosts = _dedupe_hosts(hosts)
    _HOST_CACHE[cache_key] = _HostCacheEntry(
        hosts=deduped_hosts,
        live_ip=live_ip,
        expires_at=now + _HOST_CACHE_TTL_SECONDS,
    )

    return deduped_hosts, live_ip
