"""The PoolSense integration."""
from datetime import timedelta
import logging

import async_timeout
from poolsense import PoolSense
from poolsense.exceptions import PoolSenseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ATTRIBUTION, DOMAIN

PLATFORMS = ["sensor", "binary_sensor"]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PoolSense from a config entry."""

    poolsense = PoolSense(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    auth_valid = await poolsense.test_poolsense_credentials()

    if not auth_valid:
        _LOGGER.error("Invalid authentication")
        return False

    coordinator = PoolSenseDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class PoolSenseEntity(CoordinatorEntity):
    """Implements a common class elements representing the PoolSense component."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(self, coordinator, email, description: EntityDescription):
        """Initialize poolsense sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"PoolSense {description.name}"
        self._attr_unique_id = f"{email}-{description.key}"


class PoolSenseDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold PoolSense data."""

    def __init__(self, hass, entry):
        """Initialize."""
        self.poolsense = PoolSense(
            aiohttp_client.async_get_clientsession(hass),
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
        )
        self.hass = hass
        self.entry = entry

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))

    async def _async_update_data(self):
        """Update data via library."""
        data = {}
        with async_timeout.timeout(10):
            try:
                data = await self.poolsense.get_poolsense_data()
            except (PoolSenseError) as error:
                _LOGGER.error("PoolSense query did not complete")
                raise UpdateFailed(error) from error

        return data
