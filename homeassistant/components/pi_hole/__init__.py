"""The pi_hole component."""
import logging

from hole import Hole
from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LOCATION,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)

_LOGGER = logging.getLogger(__name__)

PI_HOLE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_API_KEY): cv.string,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [PI_HOLE_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["sensor", "switch"]


async def async_setup(hass, config):
    """Set up the pi_hole integration."""

    hass.data[DOMAIN] = {}

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up Pi-hole entry."""
    # Move API key to options
    if CONF_API_KEY in entry.data:
        data = {**entry.data}
        api_key = entry.data[CONF_API_KEY]
        data.pop(CONF_API_KEY)
        hass.config_entries.async_update_entry(
            entry, data=data, options={CONF_API_KEY: api_key}
        )

    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    use_tls = entry.data[CONF_SSL]
    verify_tls = entry.data[CONF_VERIFY_SSL]
    location = entry.data[CONF_LOCATION]
    api_key = entry.options.get(CONF_API_KEY)

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    try:
        session = async_get_clientsession(hass, verify_tls)
        api = Hole(
            host, hass.loop, session, location=location, tls=use_tls, api_token=api_key,
        )
        await api.get_data()
    except HoleError as ex:
        _LOGGER.warning("Failed to connect: %s", ex)
        raise ConfigEntryNotReady

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            await api.get_data()
        except HoleError as err:
            raise UpdateFailed(f"Failed to communicating with API: {err}")

    entry.add_update_listener(async_update_listener)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload Pi-hole entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return all(
        [
            await hass.config_entries.async_forward_entry_unload(entry, platform)
            for platform in PLATFORMS
        ]
    )


class PiHoleEntity(Entity):
    """Representation of a Pi-hole entity."""

    def __init__(self, api, coordinator, name, server_unique_id):
        """Initialize a Pi-hole entity."""
        self.api = api
        self.coordinator = coordinator
        self._name = name
        self._server_unique_id = server_unique_id

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "name": self._name,
            "manufacturer": "Pi-hole",
        }

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_update(self):
        """Get the latest data from the Pi-hole API."""
        await self.coordinator.async_request_refresh()

    async def async_disable(self, duration=None):
        """Disable the service for a given duration."""
        # Do nothing. To avoid problem caused by calling service targeting all entities.
