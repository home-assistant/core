"""
Support for Netgear LTE modems.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/netgear_lte/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol
import attr
import aiohttp

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import Throttle

REQUIREMENTS = ['eternalegypt==0.0.5']

_LOGGER = logging.getLogger(__name__)

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

    host = attr.ib()
    modem = attr.ib()

    serial_number = attr.ib(init=False, default=None)
    unread_count = attr.ib(init=False, default=None)
    usage = attr.ib(init=False, default=None)
    connected = attr.ib(init=False, default=True)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Call the API to update the data."""
        import eternalegypt
        try:
            information = await self.modem.information()
            self.serial_number = information.serial_number
            self.unread_count = sum(1 for x in information.sms if x.unread)
            self.usage = information.usage
            if not self.connected:
                _LOGGER.warning("Connected to %s", self.host)
                self.connected = True
        except eternalegypt.Error:
            if self.connected:
                _LOGGER.warning("Lost connection to %s", self.host)
                self.connected = False
            self.unread_count = None
            self.usage = None


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

    modem_data = ModemData(host, modem)

    try:
        await _login(hass, modem_data, password)
    except eternalegypt.Error:
        retry_task = hass.loop.create_task(
            _retry_login(hass, modem_data, password))

        @callback
        def cleanup_retry(event):
            """Clean up retry task resources."""
            if not retry_task.done():
                retry_task.cancel()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_retry)


async def _login(hass, modem_data, password):
    """Log in and complete setup."""
    await modem_data.modem.login(password=password)
    await modem_data.async_update()
    hass.data[DATA_KEY].modem_data[modem_data.host] = modem_data

    async def cleanup(event):
        """Clean up resources."""
        await modem_data.modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)


async def _retry_login(hass, modem_data, password):
    """Sleep and retry setup."""
    import eternalegypt

    _LOGGER.warning(
        "Could not connect to %s. Will keep trying.", modem_data.host)

    modem_data.connected = False
    delay = 15

    while not modem_data.connected:
        await asyncio.sleep(delay)

        try:
            await _login(hass, modem_data, password)
        except eternalegypt.Error:
            delay = min(2*delay, 300)
