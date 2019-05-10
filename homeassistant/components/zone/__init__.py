"""Support for the definition of zones."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)
from homeassistant.core import split_entity_id
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify
from homeassistant.util.async_ import run_coroutine_threadsafe

from .config_flow import configured_zones
from .const import CONF_PASSIVE, DOMAIN, HOME_ZONE
from .zone import Zone

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Unnamed zone'
DEFAULT_PASSIVE = False
DEFAULT_RADIUS = 100

ENTITY_ID_FORMAT = 'zone.{}'
ENTITY_ID_HOME = ENTITY_ID_FORMAT.format(HOME_ZONE)

ICON_HOME = 'mdi:home'
ICON_IMPORT = 'mdi:import'

# The config that zone accepts is the same as if it has platforms.
PLATFORM_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_LATITUDE): cv.latitude,
    vol.Required(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.Coerce(float),
    vol.Optional(CONF_PASSIVE, default=DEFAULT_PASSIVE): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
}, extra=vol.ALLOW_EXTRA)


def create_zone(hass, name, latitude, longitude, radius, icon=None,
                passive=DEFAULT_PASSIVE, entity_id=None, update=True):
    """Create new zone or update an existing one."""
    return run_coroutine_threadsafe(
        async_create_zone(
            hass, name, latitude, longitude, radius, icon, passive, entity_id,
            update),
        hass.loop).result()


async def async_create_zone(hass, name, latitude, longitude, radius, icon=None,
                            passive=DEFAULT_PASSIVE, entity_id=None,
                            update=True):
    """Create new zone or update an existing one."""
    zones = hass.data[DOMAIN]
    if entity_id:
        object_id = split_entity_id(entity_id)[1]
        zone = zones.get(object_id)
        if zone:
            if update:
                zone.change(name, latitude, longitude, radius, icon, passive)
                await zone.async_update_ha_state()
            return entity_id
    else:
        entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, name, None, hass)
        object_id = split_entity_id(entity_id)[1]
    zone = Zone(hass, name, latitude, longitude, radius, icon, passive)
    zone.entity_id = entity_id
    await zone.async_update_ha_state()
    zones[object_id] = zone
    return entity_id


def remove_zone(hass, entity_id):
    """Remove existing zone."""
    run_coroutine_threadsafe(
        async_remove_zone(hass, entity_id), hass.loop).result()


async def async_remove_zone(hass, entity_id):
    """Remove existing zone."""
    zone = hass.data[DOMAIN].pop(split_entity_id(entity_id)[1], None)
    if zone:
        await zone.async_remove()


async def async_setup(hass, config):
    """Set up configured zones as well as home assistant zone if necessary."""
    hass.data[DOMAIN] = {}
    zone_entries = configured_zones(hass)
    for _, entry in config_per_platform(config, DOMAIN):
        if slugify(entry[CONF_NAME]) not in zone_entries:
            await async_create_zone(
                hass, entry[CONF_NAME], entry[CONF_LATITUDE],
                entry[CONF_LONGITUDE], entry[CONF_RADIUS],
                entry.get(CONF_ICON), entry[CONF_PASSIVE])

    if HOME_ZONE not in zone_entries:
        await async_create_zone(
            hass, hass.config.location_name, hass.config.latitude,
            hass.config.longitude, DEFAULT_RADIUS, ICON_HOME, False,
            ENTITY_ID_HOME, update=False)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up zone as config entry."""
    entry = config_entry.data
    name = entry[CONF_NAME]
    entity_id = ENTITY_ID_FORMAT.format(slugify(name))
    await async_create_zone(
        hass, name, entry[CONF_LATITUDE], entry[CONF_LONGITUDE],
        entry.get(CONF_RADIUS, DEFAULT_RADIUS), entry.get(CONF_ICON),
        entry.get(CONF_PASSIVE, DEFAULT_PASSIVE), entity_id)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    entity_id = ENTITY_ID_FORMAT.format(slugify(config_entry.data[CONF_NAME]))
    await async_remove_zone(hass, entity_id)
    return True
