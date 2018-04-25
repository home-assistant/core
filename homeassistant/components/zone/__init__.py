"""
Support for the definition of zones.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zone/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID, CONF_NAME, CONF_LATITUDE,
    CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.util import slugify

from .config_flow import configured_zones
from .const import CONF_PASSIVE, DOMAIN
from .zone import Zone

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Unnamed zone'
DEFAULT_PASSIVE = False
DEFAULT_RADIUS = 100

HOME_ZONE = 'home'
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
    """Import new configured zone as config entry."""
    zones = set()
    zone_entries = configured_zones(hass)
    for _, entry in config_per_platform(config, DOMAIN):
        name = slugify(entry[CONF_NAME])
        if name not in zone_entries:
            zones.add(name)
            hass.async_add_job(hass.config_entries.flow.async_init(
                DOMAIN, source='import', data=entry
            ))

    if HOME_ZONE not in zones and HOME_ZONE not in zone_entries:
        entry = {
            CONF_NAME: hass.config.location_name,
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
            CONF_RADIUS: DEFAULT_RADIUS,
            CONF_ICON: ICON_HOME,
            CONF_PASSIVE: False,
            CONF_ENTITY_ID: ENTITY_ID_HOME
        }
        config_entry = ConfigEntry(1, DOMAIN, 'Home', entry, 'home-assistant')
        hass.async_add_job(async_setup_entry(hass, config_entry))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up zone as config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    entry = config_entry.data
    name = entry[CONF_NAME]
    zone = Zone(hass, name, entry[CONF_LATITUDE], entry[CONF_LONGITUDE],
                entry.get(CONF_RADIUS), entry.get(CONF_ICON),
                entry.get(CONF_PASSIVE))
    zone.entity_id = entry.get(CONF_ENTITY_ID)
    if not zone.entity_id:
        zone.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, name, None, hass)
    await asyncio.wait([zone.async_update_ha_state()], loop=hass.loop)
    hass.data[DOMAIN][name] = zone
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    zones = hass.data[DOMAIN]
    zone = zones.pop(config_entry.data[CONF_NAME])
    await zone.async_remove()
    return True
