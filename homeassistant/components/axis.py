"""
Support for Axis devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/axis/
"""

import json
import logging
import os

import voluptuous as vol

from homeassistant.const import (ATTR_LOCATION, ATTR_TRIPPED,
                                 CONF_HOST, CONF_INCLUDE, CONF_NAME,
                                 CONF_PASSWORD, CONF_TRIGGER_TIME,
                                 CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.discovery import SERVICE_AXIS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component


REQUIREMENTS = ['axis==7']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'axis'
CONFIG_FILE = 'axis.conf'

AXIS_DEVICES = {}

EVENT_TYPES = ['motion', 'vmd3', 'pir', 'sound',
               'daynight', 'tampering', 'input']

PLATFORMS = ['camera']

AXIS_INCLUDE = EVENT_TYPES + PLATFORMS

AXIS_DEFAULT_HOST = '192.168.0.90'
AXIS_DEFAULT_USERNAME = 'root'
AXIS_DEFAULT_PASSWORD = 'pass'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_INCLUDE):
        vol.All(cv.ensure_list, [vol.In(AXIS_INCLUDE)]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HOST, default=AXIS_DEFAULT_HOST): cv.string,
    vol.Optional(CONF_USERNAME, default=AXIS_DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=AXIS_DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_TRIGGER_TIME, default=0): cv.positive_int,
    vol.Optional(ATTR_LOCATION, default=''): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: DEVICE_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def request_configuration(hass, name, host, serialnumber):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')

    def configuration_callback(callback_data):
        """Called when config is submitted."""
        if CONF_INCLUDE not in callback_data:
            configurator.notify_errors(request_id,
                                       "Functionality mandatory.")
            return False
        callback_data[CONF_INCLUDE] = callback_data[CONF_INCLUDE].split()
        callback_data[CONF_HOST] = host
        if CONF_NAME not in callback_data:
            callback_data[CONF_NAME] = name
        try:
            config = DEVICE_SCHEMA(callback_data)
        except vol.Invalid:
            configurator.notify_errors(request_id,
                                       "Bad input, please check spelling.")
            return False

        if setup_device(hass, config):
            config_file = _read_config(hass)
            config_file[serialnumber] = dict(config)
            del config_file[serialnumber]['hass']
            _write_config(hass, config_file)
            configurator.request_done(request_id)
        else:
            configurator.notify_errors(request_id,
                                       "Failed to register, please try again.")
            return False

    title = '{} ({})'.format(name, host)
    request_id = configurator.request_config(
        hass, title, configuration_callback,
        description='Functionality: ' + str(AXIS_INCLUDE),
        entity_picture="/static/images/logo_axis.png",
        link_name='Axis platform documentation',
        link_url='https://home-assistant.io/components/axis/',
        submit_caption="Confirm",
        fields=[
            {'id': CONF_NAME,
             'name': "Device name",
             'type': 'text'},
            {'id': CONF_USERNAME,
             'name': "User name",
             'type': 'text'},
            {'id': CONF_PASSWORD,
             'name': 'Password',
             'type': 'password'},
            {'id': CONF_INCLUDE,
             'name': "Device functionality (space separated list)",
             'type': 'text'},
            {'id': ATTR_LOCATION,
             'name': "Physical location of device (optional)",
             'type': 'text'},
            {'id': CONF_TRIGGER_TIME,
             'name': "Sensor update interval (optional)",
             'type': 'number'},
        ]
    )


def setup(hass, base_config):
    """Common setup for Axis devices."""
    def _shutdown(call):  # pylint: disable=unused-argument
        """Stop the metadatastream on shutdown."""
        for serialnumber, device in AXIS_DEVICES.items():
            _LOGGER.info("Stopping metadatastream for %s.", serialnumber)
            device.stop_metadatastream()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    def axis_device_discovered(service, discovery_info):
        """Called when axis devices has been found."""
        host = discovery_info['host']
        name = discovery_info['hostname']
        serialnumber = discovery_info['properties']['macaddress']

        if serialnumber not in AXIS_DEVICES:
            config_file = _read_config(hass)
            if serialnumber in config_file:
                try:
                    config = DEVICE_SCHEMA(config_file[serialnumber])
                except vol.Invalid as err:
                    _LOGGER.error("Bad data from %s. %s", CONFIG_FILE, err)
                    return False
                if not setup_device(hass, config):
                    _LOGGER.error("Couldn\'t set up %s", config['name'])
            else:
                request_configuration(hass, name, host, serialnumber)

    discovery.listen(hass, SERVICE_AXIS, axis_device_discovered)

    if DOMAIN in base_config:
        for device in base_config[DOMAIN]:
            config = base_config[DOMAIN][device]
            if CONF_NAME not in config:
                config[CONF_NAME] = device
            if not setup_device(hass, config):
                _LOGGER.error("Couldn\'t set up %s", config['name'])

    return True


def setup_device(hass, config):
    """Set up device."""
    from axis import AxisDevice

    config['hass'] = hass
    device = AxisDevice(config)  # Initialize device
    enable_metadatastream = False

    if device.serial_number is None:
        # If there is no serial number a connection could not be made
        _LOGGER.error("Couldn\'t connect to %s", config[CONF_HOST])
        return False

    for component in config[CONF_INCLUDE]:
        if component in EVENT_TYPES:
            # Sensors are created by device calling event_initialized
            # when receiving initialize messages on metadatastream
            device.add_event_topic(convert(component, 'type', 'subscribe'))
            if not enable_metadatastream:
                enable_metadatastream = True
        else:
            discovery.load_platform(hass, component, DOMAIN, config)

    if enable_metadatastream:
        device.initialize_new_event = event_initialized
        device.initiate_metadatastream()
    AXIS_DEVICES[device.serial_number] = device
    return True


def _read_config(hass):
    """Read Axis config."""
    path = hass.config.path(CONFIG_FILE)

    if not os.path.isfile(path):
        return {}

    with open(path) as f_handle:
        # Guard against empty file
        return json.loads(f_handle.read() or '{}')


def _write_config(hass, config):
    """Write Axis config."""
    data = json.dumps(config)
    with open(hass.config.path(CONFIG_FILE), 'w', encoding='utf-8') as outfile:
        outfile.write(data)


def event_initialized(event):
    """Register event initialized on metadatastream here."""
    hass = event.device_config('hass')
    discovery.load_platform(hass,
                            convert(event.topic, 'topic', 'platform'),
                            DOMAIN, {'axis_event': event})


class AxisDeviceEvent(Entity):
    """Representation of a Axis device event."""

    def __init__(self, axis_event):
        """Initialize the event."""
        self.axis_event = axis_event
        self._event_class = convert(self.axis_event.topic, 'topic', 'class')
        self._name = '{}_{}_{}'.format(self.axis_event.device_name,
                                       convert(self.axis_event.topic,
                                               'topic', 'type'),
                                       self.axis_event.id)
        self.axis_event.callback = self._update_callback

    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self.update()
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the event."""
        return self._name

    @property
    def device_class(self):
        """Return the class of the event."""
        return self._event_class

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the event."""
        attr = {}

        tripped = self.axis_event.is_tripped
        attr[ATTR_TRIPPED] = 'True' if tripped else 'False'

        location = self.axis_event.device_config(ATTR_LOCATION)
        if location:
            attr[ATTR_LOCATION] = location

        return attr


def convert(item, from_key, to_key):
    """Translate between Axis and HASS syntax."""
    for entry in REMAP:
        if entry[from_key] == item:
            return entry[to_key]


REMAP = [{'type': 'motion',
          'class': 'motion',
          'topic': 'tns1:VideoAnalytics/tnsaxis:MotionDetection',
          'subscribe': 'onvif:VideoAnalytics/axis:MotionDetection',
          'platform': 'binary_sensor'},
         {'type': 'vmd3',
          'class': 'motion',
          'topic': 'tns1:RuleEngine/tnsaxis:VMD3/vmd3_video_1',
          'subscribe': 'onvif:RuleEngine/axis:VMD3/vmd3_video_1',
          'platform': 'binary_sensor'},
         {'type': 'pir',
          'class': 'motion',
          'topic': 'tns1:Device/tnsaxis:Sensor/PIR',
          'subscribe': 'onvif:Device/axis:Sensor/axis:PIR',
          'platform': 'binary_sensor'},
         {'type': 'sound',
          'class': 'sound',
          'topic': 'tns1:AudioSource/tnsaxis:TriggerLevel',
          'subscribe': 'onvif:AudioSource/axis:TriggerLevel',
          'platform': 'binary_sensor'},
         {'type': 'daynight',
          'class': 'light',
          'topic': 'tns1:VideoSource/tnsaxis:DayNightVision',
          'subscribe': 'onvif:VideoSource/axis:DayNightVision',
          'platform': 'binary_sensor'},
         {'type': 'tampering',
          'class': 'safety',
          'topic': 'tns1:VideoSource/tnsaxis:Tampering',
          'subscribe': 'onvif:VideoSource/axis:Tampering',
          'platform': 'binary_sensor'},
         {'type': 'input',
          'class': 'input',
          'topic': 'tns1:Device/tnsaxis:IO/Port',
          'subscribe': 'onvif:Device/axis:IO/Port',
          'platform': 'sensor'}, ]
