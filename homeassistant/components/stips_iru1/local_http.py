"""Local HTTP helpers for DNS-first IRU1 control."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOCAL_HTTP_PASSWORD, LOCAL_HTTP_USERNAME


def _dedupe_hosts(hosts: list[str]) -> list[str]:
    out: list[str] = []
    for host in hosts:
        h = str(host or "").strip()
        if h and h not in out:
            out.append(h)
    return out


def iter_dns_host_candidates(device_unique_name: str, backend_ip: str = "") -> list[str]:
    """Build DNS-first host candidates with backend IP as a last resort."""
    hosts: list[str] = []
    unique_name = str(device_unique_name or "").strip()
    if unique_name:
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
            return s
        except ValueError:
            continue
    return ""


async def async_fetch_device_info_live_ip(
    hass: HomeAssistant,
    *,
    host: str,
    timeout: aiohttp.ClientTimeout,
) -> str:
    """Try GET /device_info on one host and return a validated IP when available."""
    session = async_get_clientsession(hass)
    auth = aiohttp.BasicAuth(LOCAL_HTTP_USERNAME, LOCAL_HTTP_PASSWORD)
    url = f"http://{host}/device_info"
    try:
        async with session.get(url, auth=auth, timeout=timeout) as response:
            if response.status >= 400:
                return ""
            try:
                payload = await response.json(content_type=None)
            except Exception:
                body = await response.text()
                try:
                    payload = json.loads(body)
                except Exception:
                    return ""
            if not isinstance(payload, dict):
                return ""
            return _extract_live_ip(payload)
    except (aiohttp.ClientError, asyncio.TimeoutError):
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
    hosts = iter_dns_host_candidates(device_unique_name, backend_ip)
    if not hosts:
        return [], ""

    probe_timeout = aiohttp.ClientTimeout(total=2, connect=1, sock_connect=1, sock_read=1.5)
    live_ip = ""
    for host in hosts:
        ip = await async_fetch_device_info_live_ip(hass, host=host, timeout=probe_timeout)
        if ip:
            live_ip = ip
            break

    if live_ip and live_ip not in hosts:
        # Keep DNS hosts first as requested; add discovered IP as fallback.
        hosts.append(live_ip)

    return _dedupe_hosts(hosts), live_ip
