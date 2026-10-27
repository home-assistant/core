"""Helper functions for the Broadlink integration."""

from __future__ import annotations

import asyncio
from base64 import b64decode
import ipaddress
import logging
import time

import broadlink_async as blk

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_DISCOVERY_LOCK = asyncio.Lock()
_DISCOVERED_CACHE: dict[str, tuple[str, blk.Device]] = {}
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL: float = 30.0


def _get_subnet_hosts(fallback_ip: str | None) -> list[str]:
    """Return list of host IP addresses to probe on the private local subnet."""
    if fallback_ip:
        try:
            ip_obj = ipaddress.ip_address(fallback_ip)
            if isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj.is_private:
                net = ipaddress.ip_network(f"{fallback_ip}/24", strict=False)
                return [str(h) for h in net.hosts()]
        except ValueError:
            pass
    return [str(h) for h in ipaddress.ip_network("192.168.1.0/24").hosts()]


async def async_find_device_by_mac(
    target_mac: str | bytes,
    fallback_ip: str | None = None,
    timeout_per_probe: float = 0.8,
) -> tuple[str, blk.Device] | None:
    """Find a Broadlink device by its MAC address across the local subnet.

    Probes private subnet addresses concurrently with bounded concurrency
    and short-term caching to prevent broadcast storms.
    """
    global _CACHE_TIMESTAMP

    if isinstance(target_mac, bytes):
        target_mac_clean = target_mac.hex().lower()
    else:
        target_mac_clean = str(target_mac).lower().replace(":", "")

    # Check cache first
    now = time.monotonic()
    if now - _CACHE_TIMESTAMP < _CACHE_TTL and target_mac_clean in _DISCOVERED_CACHE:
        _LOGGER.debug(
            "Found cached Broadlink MAC %s at %s",
            target_mac_clean,
            _DISCOVERED_CACHE[target_mac_clean][0],
        )
        return _DISCOVERED_CACHE[target_mac_clean]

    async with _DISCOVERY_LOCK:
        # Double check cache after acquiring lock
        now = time.monotonic()
        if now - _CACHE_TIMESTAMP < _CACHE_TTL and target_mac_clean in _DISCOVERED_CACHE:
            return _DISCOVERED_CACHE[target_mac_clean]

        hosts = _get_subnet_hosts(fallback_ip)
        semaphore = asyncio.Semaphore(32)

        async def probe(ip: str) -> None:
            async with semaphore:
                try:
                    dev = await asyncio.wait_for(blk.hello(ip), timeout=timeout_per_probe)
                    dev_mac = dev.mac.hex().lower()
                    _DISCOVERED_CACHE[dev_mac] = (ip, dev)
                except Exception:
                    pass

        # Probe hosts
        for attempt in range(2):
            tasks = [asyncio.create_task(probe(ip)) for ip in hosts]
            await asyncio.gather(*tasks, return_exceptions=True)
            _CACHE_TIMESTAMP = time.monotonic()

            if target_mac_clean in _DISCOVERED_CACHE:
                found = _DISCOVERED_CACHE[target_mac_clean]
                _LOGGER.info(
                    "Resolved Broadlink MAC %s to active IP %s (attempt %d)",
                    target_mac_clean,
                    found[0],
                    attempt + 1,
                )
                return found
            if attempt == 0:
                await asyncio.sleep(0.2)

    return None


def data_packet(value):
    """Decode a data packet given for a Broadlink remote."""
    value = cv.string(value)
    extra = len(value) % 4
    if extra > 0:
        value = value + ("=" * (4 - extra))
    return b64decode(value)


def mac_address(mac):
    """Validate and convert a MAC address to bytes."""
    mac = cv.string(mac)
    if len(mac) == 17:
        mac = "".join(mac[i : i + 2] for i in range(0, 17, 3))
    elif len(mac) == 14:
        mac = "".join(mac[i : i + 4] for i in range(0, 14, 5))
    elif len(mac) != 12:
        raise ValueError("Invalid MAC address")
    return bytes.fromhex(mac)


def format_mac(mac):
    """Format a MAC address."""
    return ":".join([format(octet, "02x") for octet in mac])


def import_device(hass, host):
    """Create a config flow for a device."""
    configured_hosts = {
        entry.data.get(CONF_HOST) for entry in hass.config_entries.async_entries(DOMAIN)
    }

    if host not in configured_hosts:
        task = hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: host},
        )
        hass.async_create_task(task)
