"""
Support for Envisalink devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/envisalink/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

REQUIREMENTS = ['pyenvisalink==2.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'envisalink'

DATA_EVL = 'envisalink'

CONF_CODE = 'code'
CONF_EVL_HOST = 'host'
CONF_EVL_KEEPALIVE = 'keepalive_interval'
CONF_EVL_PORT = 'port'
CONF_EVL_VERSION = 'evl_version'
CONF_PANEL_TYPE = 'panel_type'
CONF_PANIC = 'panic_type'
CONF_PARTITIONNAME = 'name'
CONF_PARTITIONS = 'partitions'
CONF_PASS = 'password'
CONF_USERNAME = 'user_name'
CONF_ZONEDUMP_INTERVAL = 'zonedump_interval'
CONF_ZONENAME = 'name'
CONF_ZONES = 'zones'
CONF_ZONETYPE = 'type'

DEFAULT_PORT = 4025
DEFAULT_EVL_VERSION = 3
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = 'opening'
DEFAULT_PANIC = 'Police'

SIGNAL_ZONE_UPDATE = 'envisalink.zones_updated'
SIGNAL_PARTITION_UPDATE = 'envisalink.partition_updated'
SIGNAL_KEYPAD_UPDATE = 'envisalink.keypad_updated'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONENAME): cv.string,
    vol.Optional(CONF_ZONETYPE, default=DEFAULT_ZONETYPE): cv.string})

PARTITION_SCHEMA = vol.Schema({
    vol.Required(CONF_PARTITIONNAME): cv.string})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EVL_HOST): cv.string,
        vol.Required(CONF_PANEL_TYPE):
            vol.All(cv.string, vol.In(['HONEYWELL', 'DSC'])),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASS): cv.string,
        vol.Required(CONF_CODE): cv.string,
        vol.Optional(CONF_PANIC, default=DEFAULT_PANIC): cv.string,
        vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
        vol.Optional(CONF_PARTITIONS): {vol.Coerce(int): PARTITION_SCHEMA},
        vol.Optional(CONF_EVL_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_EVL_VERSION, default=DEFAULT_EVL_VERSION):
            vol.All(vol.Coerce(int), vol.Range(min=3, max=4)),
        vol.Optional(CONF_EVL_KEEPALIVE, default=DEFAULT_KEEPALIVE):
            vol.All(vol.Coerce(int), vol.Range(min=15)),
        vol.Optional(
            CONF_ZONEDUMP_INTERVAL,
            default=DEFAULT_ZONEDUMP_INTERVAL): vol.Coerce(int),
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up for Envisalink devices."""
    from pyenvisalink import EnvisalinkAlarmPanel

    conf = config.get(DOMAIN)

    host = conf.get(CONF_EVL_HOST)
    port = conf.get(CONF_EVL_PORT)
    code = conf.get(CONF_CODE)
    panel_type = conf.get(CONF_PANEL_TYPE)
    panic_type = conf.get(CONF_PANIC)
    version = conf.get(CONF_EVL_VERSION)
    user = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASS)
    keep_alive = conf.get(CONF_EVL_KEEPALIVE)
    zone_dump = conf.get(CONF_ZONEDUMP_INTERVAL)
    zones = conf.get(CONF_ZONES)
    partitions = conf.get(CONF_PARTITIONS)
    sync_connect = asyncio.Future(loop=hass.loop)

    controller = EnvisalinkAlarmPanel(
        host, port, panel_type, version, user, password, zone_dump,
        keep_alive, hass.loop)
    hass.data[DATA_EVL] = controller

    @callback
    def login_fail_callback(data):
        """Handle when the evl rejects our login."""
        _LOGGER.error("The Envisalink rejected your credentials")
        sync_connect.set_result(False)

    @callback
    def connection_fail_callback(data):
        """Network failure callback."""
        _LOGGER.error("Could not establish a connection with the Envisalink")
        sync_connect.set_result(False)

    @callback
    def connection_success_callback(data):
        """Handle a successful connection."""
        _LOGGER.info("Established a connection with the Envisalink")
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_envisalink)
        sync_connect.set_result(True)

    @callback
    def zones_updated_callback(data):
        """Handle zone timer updates."""
        _LOGGER.info("Envisalink sent a zone update event. Updating zones...")
        async_dispatcher_send(hass, SIGNAL_ZONE_UPDATE, data)

    @callback
    def alarm_data_updated_callback(data):
        """Handle non-alarm based info updates."""
        _LOGGER.info("Envisalink sent new alarm info. Updating alarms...")
        async_dispatcher_send(hass, SIGNAL_KEYPAD_UPDATE, data)

    @callback
    def partition_updated_callback(data):
        """Handle partition changes thrown by evl (including alarms)."""
        _LOGGER.info("The envisalink sent a partition update event")
        async_dispatcher_send(hass, SIGNAL_PARTITION_UPDATE, data)

    @callback
    def stop_envisalink(event):
        """Shutdown envisalink connection and thread on exit."""
        _LOGGER.info("Shutting down Envisalink")
        controller.stop()

    controller.callback_zone_timer_dump = zones_updated_callback
    controller.callback_zone_state_change = zones_updated_callback
    controller.callback_partition_state_change = partition_updated_callback
    controller.callback_keypad_update = alarm_data_updated_callback
    controller.callback_login_failure = login_fail_callback
    controller.callback_login_timeout = connection_fail_callback
    controller.callback_login_success = connection_success_callback

    _LOGGER.info("Start envisalink.")
    controller.start()

    result = yield from sync_connect
    if not result:
        return False

    # Load sub-components for Envisalink
    if partitions:
        hass.async_create_task(async_load_platform(
            hass, 'alarm_control_panel', 'envisalink', {
                CONF_PARTITIONS: partitions,
                CONF_CODE: code,
                CONF_PANIC: panic_type
            }, config
        ))
        hass.async_create_task(async_load_platform(
            hass, 'sensor', 'envisalink', {
                CONF_PARTITIONS: partitions,
                CONF_CODE: code
            }, config
        ))
    if zones:
        hass.async_create_task(async_load_platform(
            hass, 'binary_sensor', 'envisalink', {
                CONF_ZONES: zones
            }, config
        ))

    return True


class EnvisalinkDevice(Entity):
    """Representation of an Envisalink device."""

    def __init__(self, name, info, controller):
        """Initialize the device."""
        self._controller = controller
        self._info = info
        self._name = name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False
