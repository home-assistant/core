"""The ATAG Integration."""
from datetime import timedelta
import logging

import async_timeout
from pyatag import AtagException, AtagOne

from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, asyncio
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "atag"
PLATFORMS = [CLIMATE, WATER_HEATER, SENSOR]


async def async_setup(hass: HomeAssistant, config):
    """Set up the Atag component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Atag integration from a config entry."""
    session = async_get_clientsession(hass)

    coordinator = AtagDataUpdateCoordinator(hass, session, entry)
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=coordinator.atag.id)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class AtagDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Atag data."""

    def __init__(self, hass, session, entry):
        """Initialize."""
        self.atag = AtagOne(session=session, **entry.data)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    async def _async_update_data(self):
        """Update data via library."""
        with async_timeout.timeout(20):
            try:
                if not await self.atag.update():
                    raise UpdateFailed("No data received")
            except AtagException as error:
                raise UpdateFailed(error)
        return self.atag.report


async def async_unload_entry(hass, entry):
    """Unload Atag config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class AtagEntity(Entity):
    """Defines a base Atag entity."""

    def __init__(self, coordinator: AtagDataUpdateCoordinator, atag_id: str) -> None:
        """Initialize the Atag entity."""
        self.coordinator = coordinator

        self._id = atag_id
        self._name = DOMAIN.title()

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self.coordinator.atag.id
        version = self.coordinator.atag.apiversion
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
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.coordinator.atag.id}-{self._id}"

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update Atag entity."""
        await self.coordinator.async_request_refresh()
