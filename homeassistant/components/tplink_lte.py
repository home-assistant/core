"""
Support for TP-Link LTE modems.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tplink_lte/
"""
import asyncio
import logging

import aiohttp
import attr
import voluptuous as vol

from homeassistant.components.notify import ATTR_TARGET
from homeassistant.const import (
    CONF_DEVICES, CONF_DISCOVERY, CONF_HOST, CONF_NAME, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession

REQUIREMENTS = ['tp-connected==0.0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tplink_lte'
DATA_KEY = 'tplink_lte'

ATTR_TARGETS = "targets"

DEFAULT_DISCOVERY = True

_TARGET_SCHEMA = vol.All(vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
}))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
        vol.Required(CONF_DEVICES): {
            vol.Optional(ATTR_TARGETS): vol.All(
                cv.ensure_list, [_TARGET_SCHEMA]),
        },
    })])
}, extra=vol.ALLOW_EXTRA)


@attr.s
class ModemData:
    """Class for modem state."""

    modem = attr.ib()


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
    """Set up TP-Link LTE component."""
    if DATA_KEY not in hass.data:
        websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True))
        hass.data[DATA_KEY] = LTEData(websession)

    tasks = [_setup_lte(hass, conf) for conf in config.get(DOMAIN, [])]
    if tasks:
        await asyncio.wait(tasks)

    for conf in config.get(DOMAIN, []):
        for notify_conf in conf[CONF_DEVICES].get(ATTR_TARGETS):
            discovery.load_platform(hass, 'notify', DOMAIN, notify_conf, conf)

    return True


async def _setup_lte(hass, lte_config, delay=0):
    """Set up a TP-Link LTE modem."""
    import tp_connected

    try:
        if delay:
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    websession = hass.data[DATA_KEY].websession
    modem = tp_connected.Modem(hostname=host, websession=websession)

    try:
        await modem.login(password=password)
    except asyncio.CancelledError:
        return
    except tp_connected.Error:
        delay = max(15, min(2*delay, 300))
        _LOGGER.warning("Retrying %s in %d seconds", host, delay)
        task = hass.loop.create_task(_setup_lte(hass, lte_config, delay))
        return

    modem_data = ModemData(modem)
    hass.data[DATA_KEY].modem_data[host] = modem_data

    async def cleanup(event):
        """Clean up resources."""
        if task is not None and not task.done():
            task.cancel()
        await modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
