"""
Support for Satel Integra devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alarmdecoder/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN, STATE_ALARM_TRIGGERED)

from satel_integra.satel_integra import AsyncSatel

DEFAULT_ALARM_NAME = 'satel_integra'
DEFAULT_PORT = 7094

REQUIREMENTS = ['satel_integra==0.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'satel_integra'

DATA_AD = 'satel_integra'

CONF_DEVICE_HOST = 'host'
CONF_DEVICE_PORT = 'port'
CONF_ZONE_NAME = 'name'
CONF_ZONE_TYPE = 'type'
CONF_ZONES = 'zones'

ZONES = 'zones'

DEFAULT_DEVICE_HOST = 'localhost'
DEFAULT_DEVICE_PORT = 10000

DEFAULT_ZONE_TYPE = 'opening'

SIGNAL_PANEL_MESSAGE = 'satel_integra.panel_message'
SIGNAL_PANEL_ARM_AWAY = 'satel_integra.panel_arm_away'
SIGNAL_PANEL_ARM_HOME = 'satel_integra.panel_arm_home'
SIGNAL_PANEL_DISARM = 'satel_integra.panel_disarm'

SIGNAL_ZONES_UPDATED = 'satel_integra.zones_updated'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONE_NAME): cv.string,
    vol.Optional(CONF_ZONE_TYPE, default=DEFAULT_ZONE_TYPE): cv.string})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE_HOST, default=DEFAULT_DEVICE_HOST): cv.string,
        vol.Required(CONF_DEVICE_PORT, default=DEFAULT_DEVICE_PORT): cv.port,
        vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
    }),
}, extra=vol.ALLOW_EXTRA)


class MockSatelIntegra:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._status = "disarmed"

    @asyncio.coroutine
    def connect(self):
        _LOGGER.info("Connecting host: %s, port %s", self._host, self._port)
        yield from asyncio.sleep(1)
        _LOGGER.debug("connected")
        return True

    @asyncio.coroutine
    def get_status(self):
        status = {}
        _LOGGER.debug("Getting status ")
        yield from asyncio.sleep(1)

        from random import randint, choice
        _LOGGER.debug("Randomly updatating status....")
        if choice([True, False]):
            _LOGGER.debug("Alarm update!")
            message = {"alarm_status": self._status}
            status[SIGNAL_PANEL_MESSAGE] = message
        else:
            _LOGGER.debug("Zones update!")
            zones = {1: 0,
                     2: 0,
                     3: 0}
            # Set one of them to "1"
            zones[randint(1, 3)] = 1
            status[ZONES] = zones
        _LOGGER.debug("got status %s", status)
        return status

    @asyncio.coroutine
    def arm_home(self, code):
        _LOGGER.info("Arming home")
        yield from asyncio.sleep(1)
        self._status = "armed_home"
        _LOGGER.debug("Armed home")

    @asyncio.coroutine
    def arm_away(self, code):
        _LOGGER.info("Arming away")
        yield from asyncio.sleep(1)
        self._status = "armed_away"
        _LOGGER.debug("Armed away")

    @asyncio.coroutine
    def disarm(self, code):
        _LOGGER.info("Disarming...")
        yield from asyncio.sleep(1)
        self._status = "disarmed"
        _LOGGER.debug("Disarmed")

    def close(self):
        _LOGGER.info("Closing alarm")
        yield from asyncio.sleep(1)
        _LOGGER.debug("Done")


@asyncio.coroutine
def async_setup(hass, config):
    """Set up for the Satel Integra devices."""

    conf = config.get(DOMAIN)

    zones = conf.get(CONF_ZONES)
    controller = False
    host = conf.get(CONF_DEVICE_HOST)
    port = conf.get(CONF_DEVICE_PORT)

    controller = AsyncSatel(host, port, zones, hass.loop)

    hass.data[DATA_AD] = controller

    result = yield from controller.connect()

    if not result:
        return False

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               lambda s: controller.close())

    hass.async_add_job(
        async_load_platform(hass, 'alarm_control_panel', DOMAIN, conf,
                            config))

    if zones:
        hass.async_add_job(async_load_platform(
            hass, 'binary_sensor', DOMAIN, {CONF_ZONES: zones}, config))

    @callback
    def alarm_status_update_callback(status):
        _LOGGER.debug("Alarm status callback, status: %s", status)

        if status["alarm_status"] == "armed":
            if status["mode"] == 0:
                hass_alarm_state = STATE_ALARM_ARMED_AWAY
            else:
                hass_alarm_status = STATE_ALARM_ARMED_HOME
        elif status["alarm_status"] == "triggered":
            hass_alarm_status = STATE_ALARM_TRIGGERED

        _LOGGER.debug("Sending hass_alarm_status: %s...", hass_alarm_status)
        async_dispatcher_send(hass, SIGNAL_PANEL_MESSAGE, hass_alarm_status)

    @callback
    def zones_update_callback(status):
        _LOGGER.debug("Zones callback , status: %s", status)
        async_dispatcher_send(hass, SIGNAL_ZONES_UPDATED, status[ZONES])

    hass.async_add_job(asyncio.ensure_future(controller.keep_alive()))
    hass.async_add_job(asyncio.ensure_future(
        controller.monitor_status(alarm_status_update_callback,
                                  zones_update_callback))
    )

    return True
