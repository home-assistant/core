"""The elmax-cloud integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .common import ElmaxCoordinator
from .const import (
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
    ELMAX_PLATFORMS,
    POLLING_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up elmax-cloud from a config entry."""
    # Create the API client object and attempt a login, so that we immediately know
    # if there is something wrong with user credentials
    coordinator = ElmaxCoordinator(
        hass=hass,
        logger=_LOGGER,
        username=entry.data[CONF_ELMAX_USERNAME],
        password=entry.data[CONF_ELMAX_PASSWORD],
        panel_id=entry.data[CONF_ELMAX_PANEL_ID],
        panel_pin=entry.data[CONF_ELMAX_PANEL_PIN],
        name=f"Elmax Cloud {entry.entry_id}",
        update_interval=timedelta(seconds=POLLING_SECONDS),
    )

    # Issue a first refresh, so that we trigger a re-auth flow if necessary
    await coordinator.async_config_entry_first_refresh()

    # Store a global reference to the coordinator for later use
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Perform platform initialization.
    await hass.config_entries.async_forward_entry_setups(entry, ELMAX_PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ELMAX_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
