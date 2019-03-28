"""Support for Netgear LTE modems."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import attr
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_PASSWORD,
    CONF_RECIPIENT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from . import sensor_types

REQUIREMENTS = ['eternalegypt==0.0.5']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
DISPATCHER_NETGEAR_LTE = 'netgear_lte_update'

DOMAIN = 'netgear_lte'
DATA_KEY = 'netgear_lte'

EVENT_SMS = 'netgear_lte_sms'

SERVICE_DELETE_SMS = 'delete_sms'

ATTR_HOST = 'host'
ATTR_SMS_ID = 'sms_id'
ATTR_FROM = 'from'
ATTR_MESSAGE = 'message'


NOTIFY_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
    vol.Optional(CONF_RECIPIENT, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=sensor_types.DEFAULT):
        vol.All(cv.ensure_list, [vol.In(sensor_types.ALL)]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(NOTIFY_DOMAIN, default={}):
            vol.All(cv.ensure_list, [NOTIFY_SCHEMA]),
        vol.Optional(SENSOR_DOMAIN, default={}):
            SENSOR_SCHEMA,
    })])
}, extra=vol.ALLOW_EXTRA)

DELETE_SMS_SCHEMA = vol.Schema({
    vol.Required(ATTR_HOST): cv.string,
    vol.Required(ATTR_SMS_ID): vol.All(cv.ensure_list, [cv.positive_int]),
})


@attr.s
class ModemData:
    """Class for modem state."""

    hass = attr.ib()
    host = attr.ib()
    modem = attr.ib()

    data = attr.ib(init=False, default=None)
    connected = attr.ib(init=False, default=True)

    async def async_update(self):
        """Call the API to update the data."""
        import eternalegypt
        try:
            self.data = await self.modem.information()
            if not self.connected:
                _LOGGER.warning("Connected to %s", self.host)
                self.connected = True
        except eternalegypt.Error:
            if self.connected:
                _LOGGER.warning("Lost connection to %s", self.host)
                self.connected = False
            self.data = None

        async_dispatcher_send(self.hass, DISPATCHER_NETGEAR_LTE)


@attr.s
class LTEData:
    """Shared state."""

    websession = attr.ib()
    modem_data = attr.ib(init=False, factory=dict)

    def get_modem_data(self, config):
        """Get modem_data for the host in config."""
        return self.modem_data.get(config[CONF_HOST])


async def async_setup(hass, config):
    """Set up Netgear LTE component."""
    if DATA_KEY not in hass.data:
        websession = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(unsafe=True))
        hass.data[DATA_KEY] = LTEData(websession)

        async def delete_sms_handler(service):
            """Apply a service."""
            host = service.data[ATTR_HOST]
            conf = {CONF_HOST: host}
            modem_data = hass.data[DATA_KEY].get_modem_data(conf)

            if not modem_data:
                _LOGGER.error(
                    "%s: host %s unavailable", SERVICE_DELETE_SMS, host)
                return

            for sms_id in service.data[ATTR_SMS_ID]:
                await modem_data.modem.delete_sms(sms_id)

        hass.services.async_register(
            DOMAIN, SERVICE_DELETE_SMS, delete_sms_handler,
            schema=DELETE_SMS_SCHEMA)

    netgear_lte_config = config[DOMAIN]

    # Set up each modem
    tasks = [_setup_lte(hass, lte_conf) for lte_conf in netgear_lte_config]
    await asyncio.wait(tasks)

    # Load platforms for each modem
    for lte_conf in netgear_lte_config:
        # Notify
        for notify_conf in lte_conf[NOTIFY_DOMAIN]:
            discovery_info = {
                CONF_HOST: lte_conf[CONF_HOST],
                CONF_NAME: notify_conf.get(CONF_NAME),
                NOTIFY_DOMAIN: notify_conf,
            }
            hass.async_create_task(discovery.async_load_platform(
                hass, NOTIFY_DOMAIN, DOMAIN, discovery_info, config))

        # Sensor
        sensor_conf = lte_conf.get(SENSOR_DOMAIN)
        discovery_info = {
            CONF_HOST: lte_conf[CONF_HOST],
            SENSOR_DOMAIN: sensor_conf,
        }
        hass.async_create_task(discovery.async_load_platform(
            hass, SENSOR_DOMAIN, DOMAIN, discovery_info, config))

    return True


async def _setup_lte(hass, lte_config):
    """Set up a Netgear LTE modem."""
    import eternalegypt

    host = lte_config[CONF_HOST]
    password = lte_config[CONF_PASSWORD]

    websession = hass.data[DATA_KEY].websession
    modem = eternalegypt.Modem(hostname=host, websession=websession)

    modem_data = ModemData(hass, host, modem)

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

    def fire_sms_event(sms):
        """Send an SMS event."""
        data = {
            ATTR_HOST: modem_data.host,
            ATTR_SMS_ID: sms.id,
            ATTR_FROM: sms.sender,
            ATTR_MESSAGE: sms.message,
        }
        hass.bus.async_fire(EVENT_SMS, data)

    await modem_data.modem.add_sms_listener(fire_sms_event)

    await modem_data.async_update()
    hass.data[DATA_KEY].modem_data[modem_data.host] = modem_data

    async def cleanup(event):
        """Clean up resources."""
        await modem_data.modem.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    async def _update(now):
        """Periodic update."""
        await modem_data.async_update()

    async_track_time_interval(hass, _update, SCAN_INTERVAL)


async def _retry_login(hass, modem_data, password):
    """Sleep and retry setup."""
    import eternalegypt

    _LOGGER.warning(
        "Could not connect to %s. Will keep trying", modem_data.host)

    modem_data.connected = False
    delay = 15

    while not modem_data.connected:
        await asyncio.sleep(delay)

        try:
            await _login(hass, modem_data, password)
        except eternalegypt.Error:
            delay = min(2*delay, 300)
