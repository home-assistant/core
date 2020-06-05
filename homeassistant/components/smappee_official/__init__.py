"""Support for the Smappee API."""
import logging

from pysmappee import Smappee

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
)
from homeassistant.util import Throttle

from .const import DATA_CLIENT, DOMAIN, MIN_TIME_BETWEEN_UPDATES, SMAPPEE_COMPONENTS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up of the Smappee Official integration."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}

    return True


async def async_setup_entry(hass, config_entry):
    """Set up of the Smappee Official integration from a config entry."""
    client_id = config_entry.data[CONF_CLIENT_ID]
    client_secret = config_entry.data[CONF_CLIENT_SECRET]
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    platform = config_entry.data[CONF_PLATFORM]

    smappee = await hass.async_add_executor_job(
        Smappee, username, password, client_id, client_secret, platform
    )
    await hass.async_add_executor_job(smappee.load_service_locations)

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = SmappeeBase(
        smappee=smappee, hass=hass
    )

    for component in SMAPPEE_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload the Smappee Official integation."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    for component in SMAPPEE_COMPONENTS:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)
    return True


class SmappeeBase:
    """An object to hold the PySmappee instance."""

    def __init__(self, smappee, hass):
        """Initialize the Smappee API wrapper class."""
        self._smappee = smappee
        self.hass = hass

    @property
    def smappee(self):
        """Return the Smappee API instance."""
        return self._smappee

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update all Smappee trends and appliance states."""
        await self.hass.async_add_executor_job(
            self._smappee.update_trends_and_appliance_states
        )
