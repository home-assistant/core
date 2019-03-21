"""Support for TP-Link LTE modems."""
import asyncio
import logging

import aiohttp
import attr
import voluptuous as vol

from homeassistant.components.notify import ATTR_TARGET
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP,
    CONF_RECIPIENT)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession

REQUIREMENTS = ['tp-connected==0.0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tplink_lte'
DATA_KEY = 'tplink_lte'

CONF_NOTIFY = 'notify'

# Deprecated in 0.88.0, invalidated in 0.91.0, remove in 0.92.0
ATTR_TARGET_INVALIDATION_VERSION = '0.91.0'

_NOTIFY_SCHEMA = vol.All(
    vol.Schema({
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_RECIPIENT): vol.All(cv.ensure_list, [cv.string])
    }),
    cv.deprecated(
        ATTR_TARGET,
        replacement_key=CONF_RECIPIENT,
        invalidation_version=ATTR_TARGET_INVALIDATION_VERSION
    ),
    cv.has_at_least_one_key(CONF_RECIPIENT),
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NOTIFY): vol.All(cv.ensure_list, [_NOTIFY_SCHEMA]),
    })])
}, extra=vol.ALLOW_EXTRA)


@attr.s
class ModemData:
    """Class for modem state."""

    host = attr.ib()
    modem = attr.ib()

    connected = attr.ib(init=False, default=True)


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

    domain_config = config.get(DOMAIN, [])

    tasks = [_setup_lte(hass, conf) for conf in domain_config]
    if tasks:
        await asyncio.wait(tasks)

    for conf in domain_config:
        for notify_conf in conf.get(CONF_NOTIFY, []):
            hass.async_create_task(discovery.async_load_platform(
                hass, 'notify', DOMAIN, notify_conf, config))

    return True


async def _setup_lte(hass, lte_config, delay=0):
    """Set up a TP-Link LTE modem."""
    import tp_connected

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    websession = hass.data[DATA_KEY].websession
    modem = tp_connected.Modem(hostname=host, websession=websession)

    modem_data = ModemData(host, modem)

    try:
        await _login(hass, modem_data, password)
    except tp_connected.Error:
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
    modem_data.connected = True
    hass.data[DATA_KEY].modem_data[modem_data.host] = modem_data

    async def cleanup(event):
        """Clean up resources."""
        await modem_data.modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)


async def _retry_login(hass, modem_data, password):
    """Sleep and retry setup."""
    import tp_connected

    _LOGGER.warning(
        "Could not connect to %s. Will keep trying.", modem_data.host)

    modem_data.connected = False
    delay = 15

    while not modem_data.connected:
        await asyncio.sleep(delay)

        try:
            await _login(hass, modem_data, password)
            _LOGGER.warning("Connected to %s", modem_data.host)
        except tp_connected.Error:
            delay = min(2*delay, 300)
