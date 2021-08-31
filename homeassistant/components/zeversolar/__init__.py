"""Local access to the zeversolar inverter integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from zeversolarlocal import api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COORDINATOR, DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Local access to the zeversolar inverter from a config entry."""

    zever_url = entry.data[CONF_URL]

    async def async_update_data() -> api.SolarData:
        """Get solar data from the zever solar inverter."""
        _LOGGER.debug("Updating zeversolar data")
        try:
            # not using a timeout here. Timeout is managed by the
            # zeversolarlocal package itself as it is a vital part of the
            # working of the package.
            return await api.solardata(zever_url, timeout=2)
        except api.ZeverError as err:
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="zeversolar",
        update_method=async_update_data,
        update_interval=timedelta(seconds=15),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
