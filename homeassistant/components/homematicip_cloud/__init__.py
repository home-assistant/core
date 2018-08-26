"""
Support for HomematicIP Cloud components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip_cloud/
"""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .config_flow import configured_haps
from .const import (
    CONF_ACCESSPOINT, CONF_AUTHTOKEN, DOMAIN, HMIPC_AUTHTOKEN, HMIPC_HAPID,
    HMIPC_NAME)
from .device import HomematicipGenericDevice  # noqa: F401
from .hap import HomematicipAuth, HomematicipHAP  # noqa: F401

REQUIREMENTS = ['homematicip==0.9.8']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN, default=[]): vol.All(cv.ensure_list, [vol.Schema({
        vol.Optional(CONF_NAME, default=''): vol.Any(cv.string),
        vol.Required(CONF_ACCESSPOINT): cv.string,
        vol.Required(CONF_AUTHTOKEN): cv.string,
    })]),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the HomematicIP Cloud component."""
    hass.data[DOMAIN] = {}

    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in configured_haps(hass):
            hass.async_add_job(hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                data={
                    HMIPC_HAPID: conf[CONF_ACCESSPOINT],
                    HMIPC_AUTHTOKEN: conf[CONF_AUTHTOKEN],
                    HMIPC_NAME: conf[CONF_NAME],
                }
            ))

    return True


async def async_setup_entry(hass, entry):
    """Set up an access point from a config entry."""
    hap = HomematicipHAP(hass, entry)
    hapid = entry.data[HMIPC_HAPID].replace('-', '').upper()
    hass.data[DOMAIN][hapid] = hap
    return await hap.async_setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hap = hass.data[DOMAIN].pop(entry.data[HMIPC_HAPID])
    return await hap.async_reset()
