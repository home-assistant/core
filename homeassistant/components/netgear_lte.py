"""
Support for Netgear LTE modems.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/netgear_lte/
"""
import asyncio
from datetime import timedelta

import voluptuous as vol
import attr
import aiohttp

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import Throttle

REQUIREMENTS = ['eternalegypt==0.0.3']

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
class ModemData:
    """Class for modem state."""

    modem = attr.ib()
    serial_number = attr.ib(init=False)
    unread_count = attr.ib(init=False)
    usage = attr.ib(init=False)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Call the API to update the data."""
        information = await self.modem.information()
        self.serial_number = information.serial_number
        self.unread_count = sum(1 for x in information.sms if x.unread)
        self.usage = information.usage


@attr.s
class LTEData:
    """Shared state."""

    websession = attr.ib()
    modem_data = attr.ib(init=False, factory=dict)

    def get_modem_data(self, config):
        """Get the requested or the only modem_data value."""
        if CONF_HOST in config:
            return self.modem_data.get(config[CONF_HOST])
        if len(self.modem_data) == 1:
            return next(iter(self.modem_data.values()))

        return None


async def async_setup(hass, config):
    """Set up Netgear LTE component."""
    if DATA_KEY not in hass.data:
        websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True))
        hass.data[DATA_KEY] = LTEData(websession)

    tasks = [_setup_lte(hass, conf) for conf in config.get(DOMAIN, [])]
    if tasks:
        await asyncio.wait(tasks)

    return True


async def _setup_lte(hass, lte_config):
    """Set up a Netgear LTE modem."""
    import eternalegypt

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    websession = hass.data[DATA_KEY].websession

    modem = eternalegypt.Modem(hostname=host, websession=websession)
    await modem.login(password=password)

    modem_data = ModemData(modem)
    await modem_data.async_update()
    hass.data[DATA_KEY].modem_data[host] = modem_data

    async def cleanup(event):
        """Clean up resources."""
        await modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
