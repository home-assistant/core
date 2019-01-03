"""
Support for the definition of zones.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zone/
"""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

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


async def async_setup(hass, config):
    """Set up configured zones as well as home assistant zone if necessary."""
    hass.data[DOMAIN] = {}
    entities = set()
    zone_entries = configured_zones(hass)
    for _, entry in config_per_platform(config, DOMAIN):
        if slugify(entry[CONF_NAME]) not in zone_entries:
            zone = Zone(hass, entry[CONF_NAME], entry[CONF_LATITUDE],
                        entry[CONF_LONGITUDE], entry.get(CONF_RADIUS),
                        entry.get(CONF_ICON), entry.get(CONF_PASSIVE))
            zone.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, entry[CONF_NAME], entities)
            hass.async_create_task(zone.async_update_ha_state())
            entities.add(zone.entity_id)

    if ENTITY_ID_HOME not in entities and HOME_ZONE not in zone_entries:
        zone = Zone(hass, hass.config.location_name,
                    hass.config.latitude, hass.config.longitude,
                    DEFAULT_RADIUS, ICON_HOME, False)
        zone.entity_id = ENTITY_ID_HOME
        hass.async_create_task(zone.async_update_ha_state())

    return True


async def async_setup_entry(hass, config_entry):
    """Set up zone as config entry."""
    entry = config_entry.data
    name = entry[CONF_NAME]
    zone = Zone(hass, name, entry[CONF_LATITUDE], entry[CONF_LONGITUDE],
                entry.get(CONF_RADIUS, DEFAULT_RADIUS), entry.get(CONF_ICON),
                entry.get(CONF_PASSIVE, DEFAULT_PASSIVE))
    zone.entity_id = async_generate_entity_id(
        ENTITY_ID_FORMAT, name, None, hass)
    hass.async_create_task(zone.async_update_ha_state())
    hass.data[DOMAIN][slugify(name)] = zone
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    zones = hass.data[DOMAIN]
    name = slugify(config_entry.data[CONF_NAME])
    zone = zones.pop(name)
    await zone.async_remove()
    return True
