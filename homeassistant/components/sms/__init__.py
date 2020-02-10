"""The sms component."""
import logging

import gammu  # pylint: disable=import-error, no-member
import voluptuous as vol

from homeassistant.const import CONF_FILE_PATH
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_FILE_PATH): cv.isfile})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Configure Gammu state machine."""
    conf = config[DOMAIN]
    device = conf.get(CONF_FILE_PATH)
   
    try:
        gateway = gammu.smsd.SMSD(gammu_conf)
    except gammu.GSMError as exc:  # pylint: disable=no-member
        _LOGGER.error("Failed to initialize, error %s", exc)
        return False
    else:
        hass.data[DOMAIN] = gateway
        return True
