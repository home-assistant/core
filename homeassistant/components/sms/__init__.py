"""The sms component."""
import logging

import gammu  # pylint: disable=import-error, no-member
import voluptuous as vol

from homeassistant.const import CONF_DEVICE
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.isdevice})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Configure Gammu state machine."""
    conf = config[DOMAIN]
    device = conf.get(CONF_DEVICE)
    gateway = gammu.StateMachine()  # pylint: disable=no-member
    gateway.SetConfig(0, dict(Device=device, Connection="at"))
    gateway.Init()
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN] = gateway
    return True
