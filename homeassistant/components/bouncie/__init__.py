"""The bouncie integration."""
from __future__ import annotations

import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CODE, CONF_REDIRECT_URI, DOMAIN, LOGGER
from .coordinator import BouncieDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bouncie from a config entry."""

    coordinator = BouncieDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        redirect_uri=entry.data[CONF_REDIRECT_URI],
        code=entry.data[CONF_CODE],
        update_interval=datetime.timedelta(seconds=60),
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
