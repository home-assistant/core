"""The Tile component."""
import asyncio
from datetime import timedelta

from pytile import async_login
from pytile.errors import SessionExpiredError, TileError

from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DOMAIN, LOGGER

PLATFORMS = ["device_tracker"]
DEVICE_TYPES = ["PHONE", "TILE"]

DEFAULT_ATTRIBUTION = "Data provided by Tile"
DEFAULT_ICON = "mdi:view-grid"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=2)

CONF_SHOW_INACTIVE = "show_inactive"


async def async_setup(hass, config):
    """Set up the Tile component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}}

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Tile as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    client = await async_login(
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        session=websession,
    )

    async def async_update_data():
        """Get new data from the API."""
        try:
            return await client.tiles.all()
        except SessionExpiredError:
            LOGGER.info("Tile session expired; creating a new one")
            await client.async_init()
        except TileError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=config_entry.title,
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_update_data,
    )

    await coordinator.async_refresh()
    hass.data[DOMAIN][DATA_COORDINATOR][config_entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a Tile config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(config_entry.entry_id)

    return unload_ok


class TileEntity(Entity):
    """Define a generic Tile entity."""

    def __init__(self, coordinator):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._name = None
        self._unique_id = None
        self.coordinator = coordinator

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return DEFAULT_ICON

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._unique_id

    @callback
    def _update_from_latest_data(self):
        """Update the entity from the latest data."""
        raise NotImplementedError

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self._update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))

        self._update_from_latest_data()

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
