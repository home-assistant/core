"""Helper functions for the Broadlink integration."""

import asyncio
from base64 import b64decode
import ipaddress
import logging
import time

import broadlink_async as blk
from broadlink_async.exceptions import BroadlinkException

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_DISCOVERY_LOCK = asyncio.Lock()
_DISCOVERED_CACHE: dict[str, tuple[str, blk.Device]] = {}
_SUBNET_LAST_SCANNED: dict[str, float] = {}
_CACHE_TTL: float = 30.0

RFC1918_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


def _get_subnet_network(fallback_ip: str | None) -> ipaddress.IPv4Network | None:
    """Return IPv4 /24 network if fallback_ip belongs to an RFC 1918 private range."""
    if fallback_ip:
        try:
            ip_obj = ipaddress.ip_address(fallback_ip)
            if isinstance(ip_obj, ipaddress.IPv4Address) and any(
                ip_obj in net for net in RFC1918_NETWORKS
            ):
                return ipaddress.IPv4Network(f"{fallback_ip}/24", strict=False)
        except ValueError:
            pass
    return None


async def async_find_device_by_mac(
    target_mac: str | bytes,
    fallback_ip: str | None = None,
    timeout_per_probe: float = 0.8,
) -> tuple[str, blk.Device] | None:
    """Find a Broadlink device by its MAC address across the local subnet.

    Probes private RFC 1918 subnet addresses concurrently with bounded concurrency
    and short-term caching to prevent broadcast storms.
    """
    if isinstance(target_mac, bytes):
        target_mac_clean = target_mac.hex().lower()
    else:
        target_mac_clean = str(target_mac).lower().replace(":", "")

    network = _get_subnet_network(fallback_ip)
    if network is None:
        _LOGGER.debug(
            "Skipping MAC rediscovery for %s: invalid or non-RFC1918 fallback IP %s",
            target_mac_clean,
            fallback_ip,
        )
        return None

    subnet_key = str(network)
    now = time.monotonic()

    # Check positive cache
    if target_mac_clean in _DISCOVERED_CACHE:
        return _DISCOVERED_CACHE[target_mac_clean]

    # Check negative cache (recent scan completed without finding target)
    if now - _SUBNET_LAST_SCANNED.get(subnet_key, 0.0) < _CACHE_TTL:
        return None

    async with _DISCOVERY_LOCK:
        now = time.monotonic()
        # Double check cache after acquiring lock
        if target_mac_clean in _DISCOVERED_CACHE:
            return _DISCOVERED_CACHE[target_mac_clean]
        if now - _SUBNET_LAST_SCANNED.get(subnet_key, 0.0) < _CACHE_TTL:
            return None

        # Discard previous discoveries for this subnet before fresh scan
        for mac, (ip_str, _) in list(_DISCOVERED_CACHE.items()):
            try:
                if ipaddress.ip_address(ip_str) in network:
                    _DISCOVERED_CACHE.pop(mac, None)
            except ValueError:
                pass

        hosts = [str(h) for h in network.hosts()]
        semaphore = asyncio.Semaphore(32)

        async def probe(ip: str) -> None:
            async with semaphore:
                try:
                    dev = await asyncio.wait_for(blk.hello(ip), timeout=timeout_per_probe)
                    dev_mac = dev.mac.hex().lower()
                    _DISCOVERED_CACHE[dev_mac] = (ip, dev)
                except (BroadlinkException, OSError, TimeoutError):
                    pass

        # Probe hosts
        for attempt in range(2):
            tasks = [asyncio.create_task(probe(ip)) for ip in hosts]
            await asyncio.gather(*tasks, return_exceptions=True)

            if target_mac_clean in _DISCOVERED_CACHE:
                _SUBNET_LAST_SCANNED[subnet_key] = time.monotonic()
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

        # Record scan completion timestamp (cached miss)
        _SUBNET_LAST_SCANNED[subnet_key] = time.monotonic()

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
