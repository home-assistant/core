"""Helper functions for the Broadlink integration."""

import asyncio
from base64 import b64decode
import ipaddress
import logging

import broadlink_async as blk

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_find_device_by_mac(
    target_mac: str | bytes,
    fallback_ip: str | None = None,
    timeout_per_probe: float = 0.8,
) -> tuple[str, blk.Device] | None:
    """Find a Broadlink device by its MAC address across the local subnet.

    Probes all addresses concurrently in milliseconds without blocking.
    """
    if isinstance(target_mac, bytes):
        target_mac_clean = target_mac.hex().lower()
    else:
        target_mac_clean = str(target_mac).lower().replace(":", "")

    # Determine subnet base prefix from fallback_ip or default to 192.168.1.
    subnet_prefix = "192.168.1."
    if fallback_ip:
        try:
            ipaddress.ip_address(fallback_ip)
            parts = fallback_ip.split(".")
            if len(parts) == 4:
                subnet_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
        except ValueError:
            pass

    async def probe(ip: str) -> tuple[str, blk.Device] | None:
        try:
            dev = await asyncio.wait_for(blk.hello(ip), timeout=timeout_per_probe)
            if dev.mac.hex().lower() == target_mac_clean:
                return (ip, dev)
        except Exception:
            pass
        return None

    # Try up to 2 attempts
    for attempt in range(2):
        tasks = [
            asyncio.create_task(probe(f"{subnet_prefix}{i}")) for i in range(1, 255)
        ]
        found = None
        try:
            for f in asyncio.as_completed(tasks):
                res = await f
                if res:
                    found = res
                    break
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()

        if found:
            _LOGGER.info(
                "Resolved Broadlink MAC %s to active IP %s (attempt %d)",
                target_mac_clean,
                found[0],
                attempt + 1,
            )
            return found
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
