"""The sms component."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SMS_GATEWAY
from .gateway import create_sms_gateway

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.isdevice})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Configure Gammu state machine."""

    sms_config = config[DOMAIN]
    device = sms_config.get(CONF_DEVICE)
    gammu_config = {"Device": device, "Connection": "at"}
    gateway = await create_sms_gateway(gammu_config, hass)
    if not gateway:
        return False
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][SMS_GATEWAY] = gateway
    return True
