"""The sms component."""
import logging

import gammu

from homeassistant.const import CONF_DEVICE

from .const import DOMAIN, STATE_MACHINE

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Configure Gammu state machine."""
    conf = config[DOMAIN]
    device = conf.get(CONF_DEVICE)
    state_machine = gammu.StateMachine()
    state_machine.SetConfig(0, dict(Device=device, Connection="at"))
    state_machine.Init()
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][STATE_MACHINE] = state_machine
    return True
