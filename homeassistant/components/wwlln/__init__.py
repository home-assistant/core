"""Support for World Wide Lightning Location Network."""
import logging

from aiowwlln import Client
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_WINDOW, DATA_CLIENT, DEFAULT_RADIUS, DEFAULT_WINDOW, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_LATITUDE): cv.latitude,
                vol.Optional(CONF_LONGITUDE): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_int,
                vol.Optional(CONF_WINDOW, default=DEFAULT_WINDOW): vol.All(
                    cv.time_period,
                    cv.positive_timedelta,
                    lambda value: value.total_seconds(),
                    vol.Range(min=DEFAULT_WINDOW.total_seconds()),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the WWLLN component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the WWLLN as config entry."""
    if not config_entry.unique_id:
        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=(
                f"{config_entry.data[CONF_LATITUDE]}, "
                f"{config_entry.data[CONF_LONGITUDE]}"
            ),
        )

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}

    websession = aiohttp_client.async_get_clientsession(hass)

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = Client(websession)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "geo_location")
    )

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
