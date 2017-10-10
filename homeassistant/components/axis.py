"""
Support for Axis devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/axis/
"""

import json
import logging
import os

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import (ATTR_LOCATION, ATTR_TRIPPED,
                                 CONF_HOST, CONF_INCLUDE, CONF_NAME,
                                 CONF_PASSWORD, CONF_PORT, CONF_TRIGGER_TIME,
                                 CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.discovery import SERVICE_AXIS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity


REQUIREMENTS = ['axis==12']

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
    vol.Optional(CONF_PORT, default=80): cv.positive_int,
    vol.Optional(ATTR_LOCATION, default=''): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: DEVICE_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_VAPIX_CALL = 'vapix_call'
SERVICE_VAPIX_CALL_RESPONSE = 'vapix_call_response'
SERVICE_CGI = 'cgi'
SERVICE_ACTION = 'action'
SERVICE_PARAM = 'param'
SERVICE_DEFAULT_CGI = 'param.cgi'
SERVICE_DEFAULT_ACTION = 'update'

SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(SERVICE_PARAM): cv.string,
    vol.Optional(SERVICE_CGI, default=SERVICE_DEFAULT_CGI): cv.string,
    vol.Optional(SERVICE_ACTION, default=SERVICE_DEFAULT_ACTION): cv.string,
})


def request_configuration(hass, config, name, host, serialnumber):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

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
            device_config = DEVICE_SCHEMA(callback_data)
        except vol.Invalid:
            configurator.notify_errors(request_id,
                                       "Bad input, please check spelling.")
            return False

        if setup_device(hass, config, device_config):
            config_file = _read_config(hass)
            config_file[serialnumber] = dict(device_config)
            del config_file[serialnumber]['hass']
            _write_config(hass, config_file)
            configurator.request_done(request_id)
        else:
            configurator.notify_errors(request_id,
                                       "Failed to register, please try again.")
            return False

    title = '{} ({})'.format(name, host)
    request_id = configurator.request_config(
        title, configuration_callback,
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
            {'id': CONF_PORT,
             'name': "HTTP port (default=80)",
             'type': 'number'},
            {'id': CONF_TRIGGER_TIME,
             'name': "Sensor update interval (optional)",
             'type': 'number'},
        ]
    )


def setup(hass, config):
    """Common setup for Axis devices."""
    def _shutdown(call):  # pylint: disable=unused-argument
        """Stop the metadatastream on shutdown."""
        for serialnumber, device in AXIS_DEVICES.items():
            _LOGGER.info("Stopping metadatastream for %s.", serialnumber)
            device.stop_metadatastream()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    def axis_device_discovered(service, discovery_info):
        """Called when axis devices has been found."""
        host = discovery_info[CONF_HOST]
        name = discovery_info['hostname']
        serialnumber = discovery_info['properties']['macaddress']

        if serialnumber not in AXIS_DEVICES:
            config_file = _read_config(hass)
            if serialnumber in config_file:
                # Device config saved to file
                try:
                    device_config = DEVICE_SCHEMA(config_file[serialnumber])
                    device_config[CONF_HOST] = host
                except vol.Invalid as err:
                    _LOGGER.error("Bad data from %s. %s", CONFIG_FILE, err)
                    return False
                if not setup_device(hass, config, device_config):
                    _LOGGER.error("Couldn\'t set up %s",
                                  device_config[CONF_NAME])
            else:
                # New device, create configuration request for UI
                request_configuration(hass, config, name, host, serialnumber)
        else:
            # Device already registered, but on a different IP
            device = AXIS_DEVICES[serialnumber]
            device.url = host
            async_dispatcher_send(hass,
                                  DOMAIN + '_' + device.name + '_new_ip',
                                  host)

    # Register discovery service
    discovery.listen(hass, SERVICE_AXIS, axis_device_discovered)

    if DOMAIN in config:
        for device in config[DOMAIN]:
            device_config = config[DOMAIN][device]
            if CONF_NAME not in device_config:
                device_config[CONF_NAME] = device
            if not setup_device(hass, config, device_config):
                _LOGGER.error("Couldn\'t set up %s", device_config[CONF_NAME])

    # Services to communicate with device.
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def vapix_service(call):
        """Service to send a message."""
        for _, device in AXIS_DEVICES.items():
            if device.name == call.data[CONF_NAME]:
                response = device.do_request(call.data[SERVICE_CGI],
                                             call.data[SERVICE_ACTION],
                                             call.data[SERVICE_PARAM])
                hass.bus.async_fire(SERVICE_VAPIX_CALL_RESPONSE, response)
                return True
        _LOGGER.info("Couldn\'t find device %s", call.data[CONF_NAME])
        return False

    # Register service with Home Assistant.
    hass.services.register(DOMAIN,
                           SERVICE_VAPIX_CALL,
                           vapix_service,
                           descriptions[DOMAIN][SERVICE_VAPIX_CALL],
                           schema=SERVICE_SCHEMA)

    return True


def setup_device(hass, config, device_config):
    """Set up device."""
    from axis import AxisDevice

    device_config['hass'] = hass
    device = AxisDevice(device_config)  # Initialize device
    enable_metadatastream = False

    if device.serial_number is None:
        # If there is no serial number a connection could not be made
        _LOGGER.error("Couldn\'t connect to %s", device_config[CONF_HOST])
        return False

    for component in device_config[CONF_INCLUDE]:
        if component in EVENT_TYPES:
            # Sensors are created by device calling event_initialized
            # when receiving initialize messages on metadatastream
            device.add_event_topic(convert(component, 'type', 'subscribe'))
            if not enable_metadatastream:
                enable_metadatastream = True
        else:
            camera_config = {
                CONF_HOST: device_config[CONF_HOST],
                CONF_NAME: device_config[CONF_NAME],
                CONF_PORT: device_config[CONF_PORT],
                CONF_USERNAME: device_config[CONF_USERNAME],
                CONF_PASSWORD: device_config[CONF_PASSWORD]
            }
            discovery.load_platform(hass,
                                    component,
                                    DOMAIN,
                                    camera_config,
                                    config)

    if enable_metadatastream:
        device.initialize_new_event = event_initialized
        if not device.initiate_metadatastream():
            hass.components.persistent_notification.create(
                'Dependency missing for sensors, '
                'please check documentation',
                title=DOMAIN,
                notification_id='axis_notification')

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
          'platform': 'binary_sensor'}, ]
