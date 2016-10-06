"""
Support for Paradox Alarms.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/paradox/

Assumes PRT3 module is connected via USB on same server as HA

Focus for getting the PRT3 to work for now.
Because the Evisalink looks very close to the IP100/1500, the evisalink code
was changed to IP100/150 and then commented out for later testing.

I'm hoping that the hub can cater for both comms modules (USB/IP).
I'm also assuming that both modules may be used at the same time.
"""
import logging
import time
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
# from homeassistant.helpers.entity import Entity
from homeassistant.components.discovery import load_platform
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)
#   STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, STATE_UNKNOWN)

REQUIREMENTS = ['pyparadox_alarm==1.0.0']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'paradox'
PLATFORM_TYPE = 'alarm_control_panel'
SENSOR_TYPE = 'binary_sensor'

PARADOX_CONTROLLER = None
PRT_MODULE = False
IP_MODULE = False

# The following items we expect to find in the yaml config file
# Most only apply to IP modules.
# Paradox Panel Type parameters
CONF_PARADOX_MODEL = 'panel_type'
CONF_COMM_MODULE = 'communication_module'
# IP100/150 parameters
CONF_IP_HOST = 'ip_host'
CONF_IP_PORT = 'ip_port'
CONF_IP_KEEPALIVE = 'keepalive_interval'
CONF_ZONEDUMP_INTERVAL = 'zonedump_interval'
# PRT3 parameters
CONF_PRT_SPEED = 'speed'
CONF_PRT_PORT = 'port'
# Panel Access parameters
CONF_CODE = 'code'
CONF_USERNAME = 'user_name'
CONF_PASS = 'password'
# Partition and zone parameters - should rather be auto discovered
CONF_ZONES = 'zones'
CONF_PARTITIONS = 'partitions'
CONF_ZONENAME = 'name'
CONF_ZONETYPE = 'type'
CONF_PARTITIONNAME = 'name'
# End of yaml config file parameters

# Defauls for when nothing is found in the yaml config file
DEFAULT_PRT_SPEED = 57600
DEFAULT_PRT_PORT = '/dev/ttyUSB0'
DEFAULT_IP_HOST = '???'
DEFAULT_IP_PORT = '???'
DEFAULT_IP_VERSION = 150
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = 'opening'

# We do not use dispatcher, so is this needed?
SIGNAL_ZONE_UPDATE = 'zones_updated'
SIGNAL_PARTITION_UPDATE = 'partition_updated'
SIGNAL_KEYPAD_UPDATE = 'keypad_updated'

# User codes to be added later to allow disarming.
PARTITION_SCHEMA = vol.Schema({
    vol.Required(CONF_PARTITIONNAME): cv.string})

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ZONENAME): cv.string,
    vol.Optional(CONF_ZONETYPE, default=DEFAULT_ZONETYPE): cv.string})


# pylint: disable=unused-argument, too-many-function-args, too-many-locals
# pylint: disable=too-many-return-statements
def setup(hass, base_config):
    """
    Set up a Home Assistant component to represent a Paradox Alarm, as a hub.

    I.e. it will consist of an alarm platform to represent each alarm area/
    partition, as well as a binary sensor platform to represent each zone.
    """
    from pyparadox_alarm.alarm_panel import ParadoxAlarmPanel
    # from pydispatch import dispatcher

    global PARADOX_CONTROLLER  # Represents the complete panel

    # Get the (paradox) domain entries from the yaml config file
    config = base_config.get(DOMAIN)

    # Needed for panel itself
    _paradox_model = config.get(CONF_PARADOX_MODEL)
    _comm_module = config.get(CONF_COMM_MODULE)
    _code = config.get(CONF_CODE)
    # _user = config.get(CONF_USERNAME)
    # _pass = config.get(CONF_PASS)
    # Needed for the PRT3
    _prt_port = config.get(CONF_PRT_PORT)
    _prt_speed = config.get(CONF_PRT_SPEED)
    '''
    # Needed for the IP100/150
    _ip_host = config.get(CONF_IP_HOST)
    _ip_port = config.get(CONF_IP_PORT)
    _zone_dump = config.get(CONF_ZONEDUMP_INTERVAL)
    _keep_alive = config.get(CONF_IP_KEEPALIVE)
    # Assign it here or rather send it all with kwargs?
    # How do we need to communicate with alarm panel
    if 'PRT3' in _comm_module:
        PRT_MODULE = True

    if 'IP' in _comm_module:
        IP_MODULE = True
    '''
    # These will be auto discovered in later versions.
    # ...if we can get the serial speed sorted.
    _zones = config.get(CONF_ZONES)
    _partitions = config.get(CONF_PARTITIONS)
    # _connect_status = {}

    if PARADOX_CONTROLLER is None:
        _LOGGER.info('Setting up %s on port %s.', _paradox_model, _prt_port)
        # Rather pass all the parameters using kwargs?
        PARADOX_CONTROLLER = ParadoxAlarmPanel(_paradox_model,
                                               _comm_module,
                                               # _user,
                                               # _pass,
                                               _prt_port,
                                               _prt_speed)
        if PARADOX_CONTROLLER is None:
            _LOGGER.info('Paradox controller not initialised')
            return False
        else:
            _LOGGER.info('Paradox controller initialised as %s.',
                         PARADOX_CONTROLLER.paradox_model)

    def update_alarm_armed_cb(area_number):
        """Process the area armed event received from alarm panel."""
        _LOGGER.debug('Area %d received armed event.', area_number)
        try:
            # Area in use on alarm panel might not be setup/defined in HA
            _affected_area = PARTITION_SCHEMA(_partitions[area_number])
            _LOGGER.debug('HA area %s to be armed.',
                          _affected_area[CONF_PARTITIONNAME])
            # This does not seem to be the correct way to set the state.

            _att = {'friendly_name': _affected_area[CONF_PARTITIONNAME]}

            hass.states.set('alarm_control_panel.' +
                            _affected_area[CONF_PARTITIONNAME],
                            STATE_ALARM_ARMED_AWAY, _att)
        except KeyError:
            _LOGGER.debug('Area %d not defined in HA.', area_number)

        return True

    def update_alarm_stay_armed_cb(area_number):
        """Process area stay armed event received from alarm panel."""
        _LOGGER.debug('Area %d received stay armed event.', area_number)
        try:
            # Area in use on alarm panel might not be setup/defined in HA
            _affected_area = PARTITION_SCHEMA(_partitions[area_number])
            _LOGGER.debug('HA area %s to be stay armed.',
                          _affected_area[CONF_PARTITIONNAME])
            # This does not seem to be the correct way to set the state.

            _att = {'friendly_name': _affected_area[CONF_PARTITIONNAME]}

            hass.states.set('alarm_control_panel.' +
                            _affected_area[CONF_PARTITIONNAME],
                            STATE_ALARM_ARMED_HOME, _att)
        except KeyError:
            _LOGGER.debug('Area %d not defined in HA.', area_number)

        return True

    def update_alarm_disarmed_cb(area_number):
        """Process area/partition disarmed event received from alarm panel."""
        _LOGGER.debug('Area %d received disarmed event.', area_number)
        try:
            # Area in use on alarm panel might not be setup/defined in HA
            _affected_area = PARTITION_SCHEMA(_partitions[area_number])
            _LOGGER.debug('HA area %s to be disarmed.',
                          _affected_area[CONF_PARTITIONNAME])

            _att = {'friendly_name': _affected_area[CONF_PARTITIONNAME]}

            # This does not seem to be the correct way to set the state.
            hass.states.set('alarm_control_panel.' +
                            _affected_area[CONF_PARTITIONNAME],
                            STATE_ALARM_DISARMED, _att)
        except KeyError:
            _LOGGER.debug('Area %d not defined in HA.', area_number)

        return True

    def update_zone_status_cb(zone_number):
        """Process the zone status change received from alarm panel."""
        # Rather define 'zone' as a constant.
        # This is not needed, the new status is getting passed in!
        _new_status = PARADOX_CONTROLLER.alarm_state['zone'][zone_number][
            'status'
            ]['open']
        _LOGGER.debug('Zone %d received new status %s.',
                      zone_number, _new_status)
        try:
            # Zone on alarm panel might not be setup/defined in HA
            _affected_zone = ZONE_SCHEMA(_zones[zone_number])
            _LOGGER.debug('HA zone %s to be updated.',
                          _affected_zone[CONF_ZONENAME])
            # This does not seem to be the correct way to set the state.
            if _new_status:
                _new_status = 'on'
            else:
                _new_status = 'off'

            _att = {'friendly_name': _affected_zone[CONF_ZONENAME],
                    'sensor_class': _affected_zone[CONF_ZONETYPE]}

            hass.states.set('binary_sensor.' + _affected_zone[CONF_ZONENAME],
                            _new_status, _att)
        except KeyError:
            _LOGGER.debug('Zone %d not defined in HA.', zone_number)

        return True

    def stop_paradox(event):
        """Shutdown Paradox connection and threads on exit."""
        _LOGGER.info("Shutting down connection to Paradox alarm.")
        PARADOX_CONTROLLER.stop()

    def start_paradox(event):
        """Startup process to connect to the Paradox alarm."""
        _LOGGER.debug('Connect to Paradox Alarm panel')
        PARADOX_CONTROLLER.start()
        # Add a test to see it is connected
        time.sleep(4)  # Give ait a few seconds to make the connection
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_paradox)

        return True

    # Overwrite the controllers default callback to call the hass functions
    PARADOX_CONTROLLER.callback_area_armed = update_alarm_armed_cb
    PARADOX_CONTROLLER.callback_area_stay_armed = update_alarm_stay_armed_cb
    PARADOX_CONTROLLER.callback_area_disarmed = update_alarm_disarmed_cb
    PARADOX_CONTROLLER.callback_zone_state_change = update_zone_status_cb

    # Connect to the Paradox Alarm.
    _connected = start_paradox(None)
    if not _connected:
        return False

    # States are in the format DOMAIN.OBJECT_ID
    hass.states.set('paradox.Paradox_State', 'Connected')

    # Load sub-components for a Paradox Alarm

    if _partitions:
        # The partitions are the Alarm Panel in Home Assistant
        _LOGGER.info('Load Paradox Alarm partitions as platform.')
        load_platform(hass, PLATFORM_TYPE, DOMAIN,
                      {CONF_PARTITIONS: _partitions,
                       'code': _code}, config)

    if _zones:
        _LOGGER.info('Load Paradox Alarm zones as platform.')
        load_platform(hass, SENSOR_TYPE, DOMAIN,
                      {CONF_ZONES: _zones}, config)

    return True
