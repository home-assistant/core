import asyncio
import logging

import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, CONF_ACCESS_TOKEN,
                                 CONF_NAME)
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import sectoralarmlib.sector as sectorlib



DOMAIN = 'sector_alarm'

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['sectoralarmlib==0.5']

CONF_EMAIL = 'email'
CONF_PASSWORD = 'password'
CONF_ALARM_ID = 'alarm_id'
CONF_CODE = "code"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN:
    vol.Schema(
        {
            vol.Required(CONF_EMAIL): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_ALARM_ID): cv.string,
            vol.Required(CONF_CODE, default=''): cv.string
        }),
},
                           extra=vol.ALLOW_EXTRA)
async def async_setup(hass, config):
    ''' Initial setup '''

    try:
        alarm = sectorlib.SectorAlarm(config[DOMAIN].get(CONF_EMAIL),config[DOMAIN].get(CONF_PASSWORD), config[DOMAIN].get(CONF_ALARM_ID), config[DOMAIN].get(CONF_CODE))
    except Exception as err:
        _LOGGER.error("Could not login to Sector Alarm. Wrong username or password?")
        return

    hass.data[DOMAIN] = alarm

    
    discovery.load_platform(hass, 'sensor', DOMAIN,
                                {CONF_NAME: DOMAIN}, config)

    discovery.load_platform(
            hass, 'alarm_control_panel', DOMAIN, {CONF_CODE: config[DOMAIN][CONF_CODE], CONF_ALARM_ID: config[DOMAIN][CONF_ALARM_ID]}, config)

    return True
