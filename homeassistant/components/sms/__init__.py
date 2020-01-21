"""The sms component."""

DOMAIN = "sms"

import logging
import gammu
from homeassistant.const import CONF_DEVICE

_LOGGER = logging.getLogger(__name__)

STATE_MACHINE = gammu.StateMachine()
CONF_PHONE_NUMBER = "phone_number"

async def async_setup(hass, config):
    conf = config[DOMAIN]
    device = conf.get(CONF_DEVICE)
    STATE_MACHINE.SetConfig(0,dict(Device = device, Connection = 'at'))
    STATE_MACHINE.Init()
    return True
