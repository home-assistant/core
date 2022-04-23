"""The Elro Connects integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from elro.api import K1

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CONNECTOR_ID, CONF_UPDATE_INTERVAL, DOMAIN
from .device import ElroConnectsK1

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SIREN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elro Connects from a config entry."""

    async def _async_update_data() -> dict[int, dict]:
        """Update data via API."""
        try:
            await elro_connects_api.async_update()
        except K1.K1ConnectionError as err:
            raise UpdateFailed(err) from err
        return elro_connects_api.data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN.title(),
        update_method=_async_update_data,
        update_interval=timedelta(seconds=entry.data[CONF_UPDATE_INTERVAL]),
    )
    elro_connects_api = ElroConnectsK1(
        coordinator,
        entry.data[CONF_HOST],
        entry.data[CONF_CONNECTOR_ID],
        entry.data[CONF_PORT],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = elro_connects_api

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
