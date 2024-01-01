"""The Aseko Pool Live integration."""
from __future__ import annotations

import logging

from aioaseko import APIUnavailable, MobileAccount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import AsekoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aseko Pool Live from a config entry."""
    account = MobileAccount(
        async_get_clientsession(hass), access_token=entry.data[CONF_ACCESS_TOKEN]
    )

    try:
        units = await account.get_units()
    except APIUnavailable as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = []

    for unit in units:
        coordinator = AsekoDataUpdateCoordinator(hass, unit)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id].append((unit, coordinator))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
