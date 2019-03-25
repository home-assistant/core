import logging
import voluptuous as vol
import sectoralarmlib.sector as sectorlib
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_NAME)
from homeassistant.helpers import discovery

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
    """Initial setup for Sector Alarm."""
    try:
        alarm = sectorlib.SectorAlarm(config[DOMAIN].get(CONF_EMAIL),
                                      config[DOMAIN].get(CONF_PASSWORD),
                                      config[DOMAIN].get(CONF_ALARM_ID),
                                      config[DOMAIN].get(CONF_CODE))
    except Exception:
        _LOGGER.error("Could not login. Wrong username or password?")
        return

    hass.data[DOMAIN] = alarm

    discovery.load_platform(hass, 'sensor', DOMAIN,
                            {CONF_NAME: DOMAIN}, config)

    discovery.load_platform(
        hass, 'alarm_control_panel',
        DOMAIN,
        {CONF_CODE: config[DOMAIN][CONF_CODE],
         CONF_ALARM_ID: config[DOMAIN][CONF_ALARM_ID]},
        config)

    return True
