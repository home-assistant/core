"""The loqed integration."""
from __future__ import annotations

import logging
import re

from loqedAPI import loqed

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import LoqedDataCoordinator

PLATFORMS: list[str] = [Platform.LOCK, Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up loqed from a config entry."""
    websession = async_get_clientsession(hass)
    host = entry.data["bridge_ip"]
    apiclient = loqed.APIClient(websession, f"http://{host}")
    api = loqed.LoqedAPI(apiclient)

    lock = await api.async_get_lock(
        entry.data["lock_key_key"],
        entry.data["bridge_key"],
        int(entry.data["lock_key_local_id"]),
        re.sub(r"LOQED-([a-f0-9]+)\.local", r"\1", entry.data["bridge_mdns_hostname"]),
    )
    coordinator = LoqedDataCoordinator(hass, api, lock, entry)
    await coordinator.ensure_webhooks()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    await coordinator.remove_webhooks()

    return unload_ok
