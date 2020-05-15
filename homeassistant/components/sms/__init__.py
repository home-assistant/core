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


def setup(hass, config):
    """Configure Gammu state machine."""
    conf = config[DOMAIN]
    device = conf.get(CONF_DEVICE)
    gateway = gammu.StateMachine()  # pylint: disable=no-member
    try:
        gateway.SetConfig(0, dict(Device=device, Connection="at"))
        gateway.Init()
    except gammu.GSMError as exc:  # pylint: disable=no-member
        _LOGGER.error("Failed to initialize, error %s", exc)
        return False
    else:
        hass.data[DOMAIN] = gateway
        return True
