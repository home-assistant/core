"""
Support for Envisalink devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/envisalink/
"""
import logging
import time
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
from homeassistant.components.discovery import load_platform

REQUIREMENTS = ['pyenvisalink==1.7', 'pydispatcher==2.0.5']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'envisalink'

EVL_CONTROLLER = None

CONF_EVL_HOST = 'host'
CONF_EVL_PORT = 'port'
CONF_PANEL_TYPE = 'panel_type'
CONF_EVL_VERSION = 'evl_version'
CONF_CODE = 'code'
CONF_USERNAME = 'user_name'
CONF_PASS = 'password'
CONF_EVL_KEEPALIVE = 'keepalive_interval'
CONF_ZONEDUMP_INTERVAL = 'zonedump_interval'
CONF_ZONES = 'zones'
CONF_PARTITIONS = 'partitions'

CONF_ZONENAME = 'name'
CONF_ZONETYPE = 'type'
CONF_PARTITIONNAME = 'name'
CONF_PANIC = 'panic_type'

DEFAULT_PORT = 4025
DEFAULT_EVL_VERSION = 3
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = 'opening'
DEFAULT_PANIC = 'Police'

SIGNAL_ZONE_UPDATE = 'zones_updated'
SIGNAL_PARTITION_UPDATE = 'partition_updated'
SIGNAL_KEYPAD_UPDATE = 'keypad_updated'

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
        vol.Optional(CONF_ZONEDUMP_INTERVAL,
                     default=DEFAULT_ZONEDUMP_INTERVAL):
            vol.All(vol.Coerce(int), vol.Range(min=15)),
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=unused-argument, too-many-function-args, too-many-locals
# pylint: disable=too-many-return-statements
def setup(hass, base_config):
    """Common setup for Envisalink devices."""
    from pyenvisalink import EnvisalinkAlarmPanel
    from pydispatch import dispatcher

    global EVL_CONTROLLER

    config = base_config.get(DOMAIN)

    _host = config.get(CONF_EVL_HOST)
    _port = config.get(CONF_EVL_PORT)
    _code = config.get(CONF_CODE)
    _panel_type = config.get(CONF_PANEL_TYPE)
    _panic_type = config.get(CONF_PANIC)
    _version = config.get(CONF_EVL_VERSION)
    _user = config.get(CONF_USERNAME)
    _pass = config.get(CONF_PASS)
    _keep_alive = config.get(CONF_EVL_KEEPALIVE)
    _zone_dump = config.get(CONF_ZONEDUMP_INTERVAL)
    _zones = config.get(CONF_ZONES)
    _partitions = config.get(CONF_PARTITIONS)
    _connect_status = {}
    EVL_CONTROLLER = EnvisalinkAlarmPanel(_host,
                                          _port,
                                          _panel_type,
                                          _version,
                                          _user,
                                          _pass,
                                          _zone_dump,
                                          _keep_alive,
                                          hass.loop)

    def login_fail_callback(data):
        """Callback for when the evl rejects our login."""
        _LOGGER.error("The envisalink rejected your credentials.")
        _connect_status['fail'] = 1

    def connection_fail_callback(data):
        """Network failure callback."""
        _LOGGER.error("Could not establish a connection with the envisalink.")
        _connect_status['fail'] = 1

    def connection_success_callback(data):
        """Callback for a successful connection."""
        _LOGGER.info("Established a connection with the envisalink.")
        _connect_status['success'] = 1

    def zones_updated_callback(data):
        """Handle zone timer updates."""
        _LOGGER.info("Envisalink sent a zone update event.  Updating zones...")
        dispatcher.send(signal=SIGNAL_ZONE_UPDATE,
                        sender=None,
                        zone=data)

    def alarm_data_updated_callback(data):
        """Handle non-alarm based info updates."""
        _LOGGER.info("Envisalink sent new alarm info. Updating alarms...")
        dispatcher.send(signal=SIGNAL_KEYPAD_UPDATE,
                        sender=None,
                        partition=data)

    def partition_updated_callback(data):
        """Handle partition changes thrown by evl (including alarms)."""
        _LOGGER.info("The envisalink sent a partition update event.")
        dispatcher.send(signal=SIGNAL_PARTITION_UPDATE,
                        sender=None,
                        partition=data)

    def stop_envisalink(event):
        """Shutdown envisalink connection and thread on exit."""
        _LOGGER.info("Shutting down envisalink.")
        EVL_CONTROLLER.stop()

    def start_envisalink(event):
        """Startup process for the Envisalink."""
        hass.loop.call_soon_threadsafe(EVL_CONTROLLER.start)
        for _ in range(10):
            if 'success' in _connect_status:
                hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_envisalink)
                return True
            elif 'fail' in _connect_status:
                return False
            else:
                time.sleep(1)

        _LOGGER.error("Timeout occurred while establishing evl connection.")
        return False

    EVL_CONTROLLER.callback_zone_timer_dump = zones_updated_callback
    EVL_CONTROLLER.callback_zone_state_change = zones_updated_callback
    EVL_CONTROLLER.callback_partition_state_change = partition_updated_callback
    EVL_CONTROLLER.callback_keypad_update = alarm_data_updated_callback
    EVL_CONTROLLER.callback_login_failure = login_fail_callback
    EVL_CONTROLLER.callback_login_timeout = connection_fail_callback
    EVL_CONTROLLER.callback_login_success = connection_success_callback

    _result = start_envisalink(None)
    if not _result:
        return False

    # Load sub-components for Envisalink
    if _partitions:
        load_platform(hass, 'alarm_control_panel', 'envisalink',
                      {CONF_PARTITIONS: _partitions,
                       CONF_CODE: _code,
                       CONF_PANIC: _panic_type}, base_config)
        load_platform(hass, 'sensor', 'envisalink',
                      {CONF_PARTITIONS: _partitions,
                       CONF_CODE: _code}, base_config)
    if _zones:
        load_platform(hass, 'binary_sensor', 'envisalink',
                      {CONF_ZONES: _zones}, base_config)

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
