"""Support for World Wide Lightning Location Network."""
import logging

from aiowwlln import Client

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_WINDOW,
    DATA_CLIENT,
    DEFAULT_RADIUS,
    DEFAULT_WINDOW,
    DOMAIN,
    TOPIC_OPTIONS_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the WWLLN component."""
    hass.data[DOMAIN] = {DATA_CLIENT: {}}

    return True


@callback
def _standardize_config_entry(hass, config_entry):
    """Ensure that config entries have appropriate properties."""
    entry_updates = {}

    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates[
            "unique_id"
        ] = f"{config_entry.data[CONF_LATITUDE], config_entry.data[CONF_LONGITUDE]}"
    if not config_entry.options:
        # If the config entry doesn't already have any options set, set defaults:
        entry_updates["options"] = {
            CONF_RADIUS: DEFAULT_RADIUS,
            CONF_WINDOW: DEFAULT_WINDOW,
        }

    if not entry_updates:
        return

    hass.config_entries.async_update_entry(config_entry, **entry_updates)


async def async_setup_entry(hass, config_entry):
    """Set up the WWLLN as config entry."""
    _standardize_config_entry(hass, config_entry)

    websession = aiohttp_client.async_get_clientsession(hass)
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = Client(websession)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "geo_location")
    )

    config_entry.add_update_listener(async_update_options)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an WWLLN config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)

    await hass.config_entries.async_forward_entry_unload(config_entry, "geo_location")

    return True


async def async_migrate_entry(hass, config_entry):
    """Migrate the config entry upon new versions."""
    version = config_entry.version
    data = config_entry.data

    default_total_seconds = DEFAULT_WINDOW.total_seconds()

    _LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Expanding the default window to 1 hour (if needed):
    if version == 1:
        if data[CONF_WINDOW] < default_total_seconds:
            data[CONF_WINDOW] = default_total_seconds
        version = config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=data)
        _LOGGER.info("Migration to version %s successful", version)

    return True


async def async_update_options(hass, config_entry):
    """Handle an options update."""
    async_dispatcher_send(
        hass, TOPIC_OPTIONS_UPDATE.format(config_entry.unique_id), config_entry.options
    )
