"""The loqed integration."""

from __future__ import annotations

import re

import aiohttp
from loqedAPI import loqed

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import LoqedConfigEntry, LoqedDataCoordinator

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LoqedConfigEntry) -> bool:
    """Set up loqed from a config entry."""
    websession = async_get_clientsession(hass)
    host = entry.data["bridge_ip"]
    apiclient = loqed.APIClient(websession, f"http://{host}")
    api = loqed.LoqedAPI(apiclient)

    try:
        lock = await api.async_get_lock(
            entry.data["lock_key_key"],
            entry.data["bridge_key"],
            int(entry.data["lock_key_local_id"]),
            re.sub(
                r"LOQED-([a-f0-9]+)\.local", r"\1", entry.data["bridge_mdns_hostname"]
            ),
        )
    except (
        TimeoutError,
        aiohttp.ClientError,
    ) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to bridge at {host}") from ex
    coordinator = LoqedDataCoordinator(hass, entry, api, lock)
    await coordinator.ensure_webhooks()

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoqedConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.remove_webhooks()

    return unload_ok
