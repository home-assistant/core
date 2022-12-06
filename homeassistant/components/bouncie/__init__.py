"""The bouncie integration."""
from __future__ import annotations

import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import BouncieDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bouncie from a config entry."""

    update_interval = datetime.timedelta(seconds=60)
    session = async_get_clientsession(hass=hass)
    coordinator = BouncieDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        client_id=entry.data["client_id"],
        client_secret=entry.data["client_secret"],
        redirect_uri=entry.data["redirect_uri"],
        code=entry.data["code"],
        session=session,
        update_interval=update_interval,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
