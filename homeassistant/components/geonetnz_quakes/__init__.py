"""The GeoNet NZ Quakes integration."""
import logging

import voluptuous as vol

from .const import CONF_MINIMUM_MAGNITUDE, CONF_MMI, DEFAULT_MMI, \
    DEFAULT_MINIMUM_MAGNITUDE, DEFAULT_RADIUS
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS,
    CONF_SCAN_INTERVAL)
from homeassistant.helpers import config_validation as cv

from .config_flow import configured_instances
from .const import (
    DEFAULT_RADIUS, DOMAIN, FEED,
    DEFAULT_SCAN_INTERVAL)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_MMI, default=DEFAULT_MMI):
            vol.All(vol.Coerce(int), vol.Range(min=-1, max=8)),
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS):
            vol.Coerce(float),
        vol.Optional(CONF_MINIMUM_MAGNITUDE,
                     default=DEFAULT_MINIMUM_MAGNITUDE):
            vol.All(vol.Coerce(float), vol.Range(min=0))
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the GeoNet NZ Quakes component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    mmi = conf.get(CONF_MMI, DEFAULT_MMI)
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    identifier = '{0}, {1}'.format(latitude, longitude)
    if identifier in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: conf[CONF_RADIUS],
                CONF_MINIMUM_MAGNITUDE: conf[CONF_MINIMUM_MAGNITUDE],
                CONF_MMI: mmi,
                CONF_SCAN_INTERVAL: scan_interval
            }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the GeoNet NZ Quakes component as config entry."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][FEED] = {}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, 'geo_location'))

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an GeoNet NZ Quakes component config entry."""
    manager = hass.data[DOMAIN][FEED].pop(config_entry.entry_id)
    await manager.async_stop()

    await hass.config_entries.async_forward_entry_unload(
        config_entry, 'geo_location')

    return True
