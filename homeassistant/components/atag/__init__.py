"""The ATAG Integration."""
from datetime import timedelta
import logging

import async_timeout
from pyatag import AtagException, AtagOne

from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "atag"
PLATFORMS = [CLIMATE, WATER_HEATER, SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Atag integration from a config entry."""

    async def _async_update_data():
        """Update data via library."""
        with async_timeout.timeout(20):
            try:
                await atag.update()
            except AtagException as err:
                raise UpdateFailed(err) from err
        return atag

    atag = AtagOne(
        session=async_get_clientsession(hass), **entry.data, device=entry.unique_id
    )
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN.title(),
        update_method=_async_update_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=atag.id)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload Atag config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class AtagEntity(CoordinatorEntity):
    """Defines a base Atag entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, atag_id: str) -> None:
        """Initialize the Atag entity."""
        super().__init__(coordinator)

        self._id = atag_id
        self._name = DOMAIN.title()

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self.coordinator.data.id
        version = self.coordinator.data.apiversion
        return {
            "identifiers": {(DOMAIN, device)},
            "name": "Atag Thermostat",
            "model": "Atag One",
            "sw_version": version,
            "manufacturer": "Atag",
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.coordinator.data.id}-{self._id}"
