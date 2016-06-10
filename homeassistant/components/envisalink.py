"""
Support for Envisalink devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/envisalink/
"""
import logging
import time
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
from homeassistant.components.discovery import load_platform
from homeassistant.util import convert

REQUIREMENTS = ['pyenvisalink==0.5', 'pydispatcher==2.0.5']

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

DEFAULT_PORT = 4025
DEFAULT_EVL_VERSION = 3
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30

SIGNAL_ZONE_UPDATE = 'zones_updated'
SIGNAL_PARTITION_UPDATE = 'partition_updated'
SIGNAL_KEYPAD_UPDATE = 'keypad_updated'

REQ_VAR_ERR = "Missing required variable: {0}"
INVALID_PANEL_ERR = REQ_VAR_ERR + " Valid values are HONEYWELL/DSC."


# pylint: disable=unused-argument, too-many-function-args, too-many-locals
# pylint: disable=too-many-return-statements
def setup(hass, base_config):
    """Common setup for Envisalink devices."""
    from pyenvisalink import EnvisalinkAlarmPanel
    from pydispatch import dispatcher

    global EVL_CONTROLLER

    config = base_config.get(DOMAIN)

    if config.get(CONF_EVL_HOST) is None:
        _LOGGER.error(str.format(REQ_VAR_ERR, CONF_EVL_HOST))
        return False

    if config.get(CONF_PANEL_TYPE) is None:
        _LOGGER.error(str.format(INVALID_PANEL_ERR, CONF_PANEL_TYPE))
        return False

    if config.get(CONF_USERNAME) is None:
        _LOGGER.error(str.format(REQ_VAR_ERR, CONF_USERNAME))
        return False

    if config.get(CONF_PASS) is None:
        _LOGGER.error(str.format(REQ_VAR_ERR, CONF_PASS))
        return False

    if config.get(CONF_ZONES) is None:
        _LOGGER.error(str.format(REQ_VAR_ERR, CONF_ZONES))
        return False

    if config.get(CONF_PARTITIONS) is None:
        _LOGGER.error(str.format(REQ_VAR_ERR, CONF_PARTITIONS))
        return False

    _host = config.get(CONF_EVL_HOST)
    _port = convert(config.get(CONF_EVL_PORT), int, DEFAULT_PORT)
    _code = config.get(CONF_CODE)
    _panel_type = config.get(CONF_PANEL_TYPE)
    _version = convert(config.get(CONF_EVL_VERSION), int, DEFAULT_EVL_VERSION)
    _user = config.get(CONF_USERNAME)
    _pass = config.get(CONF_PASS)
    _keep_alive = convert(config.get(CONF_EVL_KEEPALIVE),
                         int,
                         DEFAULT_KEEPALIVE)
    _zone_dump = convert(config.get(CONF_ZONEDUMP_INTERVAL),
                        int,
                        DEFAULT_ZONEDUMP_INTERVAL)
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
                                          _keep_alive)

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
        dispatcher.send(signal=SIGNAL_ZONE_UPDATE, sender=None)

    def alarm_data_updated_callback(data):
        """Handle non-alarm based info updates."""
        _LOGGER.info("Envisalink sent new alarm info. Updating alarms...")
        dispatcher.send(signal=SIGNAL_KEYPAD_UPDATE, sender=None)

    def partition_updated_callback(data):
        """Handle partition changes thrown by evl (including alarms)."""
        _LOGGER.info("The envisalink sent a partition update event.")
        dispatcher.send(signal=SIGNAL_PARTITION_UPDATE, sender=None)

    def stop_envisalink(event):
        """Shutdown envisalink connection and thread on exit."""
        _LOGGER.info("Shutting down envisalink.")
        EVL_CONTROLLER.stop()

    def start_envisalink(event):
        """Startup process for the envisalink."""
        EVL_CONTROLLER.start()
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
    if _result:
        # Load sub-components for envisalink
        for comp_name in (['binary_sensor', 'alarm_control_panel', 'sensor']):
            load_platform(hass, comp_name, 'envisalink',
                          {'zones': _zones, 'partitions': _partitions,
                           'code': _code}, config)

    return _result


class EnvisalinkDevice(Entity):
    """Representation of an envisalink devicetity."""

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
