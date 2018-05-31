"""
Support for Netgear LTE modems.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/netgear_lte/
"""
import asyncio
from datetime import timedelta

import voluptuous as vol
import attr

from homeassistant.const import CONF_HOST, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['eternalegypt==0.0.1']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

DOMAIN = 'netgear_lte'
DATA_KEY = 'netgear_lte'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })])
}, extra=vol.ALLOW_EXTRA)


@attr.s
class LTEData:
    """Class for LTE state."""

    eternalegypt = attr.ib()
    unread_count = attr.ib(init=False)
    usage = attr.ib(init=False)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Call the API to update the data."""
        information = await self.eternalegypt.information()
        self.unread_count = sum(1 for x in information.sms if x.unread)
        self.usage = information.usage


@attr.s
class LTEHostData:
    """Container for LTE states."""

    hostdata = attr.ib(init=False, factory=dict)

    def get(self, config):
        """Get the requested or the only hostdata value."""
        if CONF_HOST in config:
            return self.hostdata.get(config[CONF_HOST])
        elif len(self.hostdata) == 1:
            return next(iter(self.hostdata.values()))

        return None


async def async_setup(hass, config):
    """Set up Netgear LTE component."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = LTEHostData()

    tasks = [_setup_lte(hass, conf) for conf in config.get(DOMAIN, [])]
    if tasks:
        await asyncio.wait(tasks)

    return True


async def _setup_lte(hass, lte_config):
    """Set up a Netgear LTE modem."""
    import eternalegypt

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    eternalegypt = eternalegypt.LB2120(host, password)
    lte_data = LTEData(eternalegypt)
    await lte_data.async_update()
    hass.data[DATA_KEY].hostdata[host] = lte_data
