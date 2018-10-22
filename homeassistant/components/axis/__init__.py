"""
Support for Axis devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/axis/
"""
import logging

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_AXIS
from homeassistant.const import (
    ATTR_LOCATION, CONF_EVENT, CONF_HOST, CONF_INCLUDE,
    CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_TRIGGER_TIME, CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['axis==16']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'axis'
CONFIG_FILE = 'axis.conf'

EVENT_TYPES = ['motion', 'vmd3', 'pir', 'sound',
               'daynight', 'tampering', 'input']

PLATFORMS = ['camera']

AXIS_INCLUDE = EVENT_TYPES + PLATFORMS

AXIS_DEFAULT_HOST = '192.168.0.90'
AXIS_DEFAULT_USERNAME = 'root'
AXIS_DEFAULT_PASSWORD = 'pass'
DEFAULT_PORT = 80

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_INCLUDE):
        vol.All(cv.ensure_list, [vol.In(AXIS_INCLUDE)]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HOST, default=AXIS_DEFAULT_HOST): cv.string,
    vol.Optional(CONF_USERNAME, default=AXIS_DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=AXIS_DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_TRIGGER_TIME, default=0): cv.positive_int,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
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
        """Call when configuration is submitted."""
        if CONF_INCLUDE not in callback_data:
            configurator.notify_errors(
                request_id, "Functionality mandatory.")
            return False

        callback_data[CONF_INCLUDE] = callback_data[CONF_INCLUDE].split()
        callback_data[CONF_HOST] = host

        if CONF_NAME not in callback_data:
            callback_data[CONF_NAME] = name

        try:
            device_config = DEVICE_SCHEMA(callback_data)
        except vol.Invalid:
            configurator.notify_errors(
                request_id, "Bad input, please check spelling.")
            return False

        if setup_device(hass, config, device_config):
            config_file = load_json(hass.config.path(CONFIG_FILE))
            config_file[serialnumber] = dict(device_config)
            save_json(hass.config.path(CONFIG_FILE), config_file)
            configurator.request_done(request_id)
        else:
            configurator.notify_errors(
                request_id, "Failed to register, please try again.")
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
    """Set up for Axis devices."""
    hass.data[DOMAIN] = {}

    def _shutdown(call):
        """Stop the event stream on shutdown."""
        for serialnumber, device in hass.data[DOMAIN].items():
            _LOGGER.info("Stopping event stream for %s.", serialnumber)
            device.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    def axis_device_discovered(service, discovery_info):
        """Call when axis devices has been found."""
        host = discovery_info[CONF_HOST]
        name = discovery_info['hostname']
        serialnumber = discovery_info['properties']['macaddress']

        if serialnumber not in hass.data[DOMAIN]:
            config_file = load_json(hass.config.path(CONFIG_FILE))
            if serialnumber in config_file:
                # Device config previously saved to file
                try:
                    device_config = DEVICE_SCHEMA(config_file[serialnumber])
                    device_config[CONF_HOST] = host
                except vol.Invalid as err:
                    _LOGGER.error("Bad data from %s. %s", CONFIG_FILE, err)
                    return False
                if not setup_device(hass, config, device_config):
                    _LOGGER.error(
                        "Couldn't set up %s", device_config[CONF_NAME])
            else:
                # New device, create configuration request for UI
                request_configuration(hass, config, name, host, serialnumber)
        else:
            # Device already registered, but on a different IP
            device = hass.data[DOMAIN][serialnumber]
            device.config.host = host
            dispatcher_send(hass, DOMAIN + '_' + device.name + '_new_ip', host)

    # Register discovery service
    discovery.listen(hass, SERVICE_AXIS, axis_device_discovered)

    if DOMAIN in config:
        for device in config[DOMAIN]:
            device_config = config[DOMAIN][device]
            if CONF_NAME not in device_config:
                device_config[CONF_NAME] = device
            if not setup_device(hass, config, device_config):
                _LOGGER.error("Couldn't set up %s", device_config[CONF_NAME])

    def vapix_service(call):
        """Service to send a message."""
        for device in hass.data[DOMAIN].values():
            if device.name == call.data[CONF_NAME]:
                response = device.vapix.do_request(
                    call.data[SERVICE_CGI],
                    call.data[SERVICE_ACTION],
                    call.data[SERVICE_PARAM])
                hass.bus.fire(SERVICE_VAPIX_CALL_RESPONSE, response)
                return True
        _LOGGER.info("Couldn't find device %s", call.data[CONF_NAME])
        return False

    # Register service with Home Assistant.
    hass.services.register(
        DOMAIN, SERVICE_VAPIX_CALL, vapix_service, schema=SERVICE_SCHEMA)
    return True


def setup_device(hass, config, device_config):
    """Set up an Axis device."""
    import axis

    def signal_callback(action, event):
        """Call to configure events when initialized on event stream."""
        if action == 'add':
            event_config = {
                CONF_EVENT: event,
                CONF_NAME: device_config[CONF_NAME],
                ATTR_LOCATION: device_config[ATTR_LOCATION],
                CONF_TRIGGER_TIME: device_config[CONF_TRIGGER_TIME]
            }
            component = event.event_platform
            discovery.load_platform(
                hass, component, DOMAIN, event_config, config)

    event_types = [
        event
        for event in device_config[CONF_INCLUDE]
        if event in EVENT_TYPES
    ]

    device = axis.AxisDevice(
        loop=hass.loop, host=device_config[CONF_HOST],
        username=device_config[CONF_USERNAME],
        password=device_config[CONF_PASSWORD],
        port=device_config[CONF_PORT], web_proto='http',
        event_types=event_types, signal=signal_callback)

    try:
        hass.data[DOMAIN][device.vapix.serial_number] = device

    except axis.Unauthorized:
        _LOGGER.error("Credentials for %s are faulty",
                      device_config[CONF_HOST])
        return False

    except axis.RequestError:
        return False

    device.name = device_config[CONF_NAME]

    for component in device_config[CONF_INCLUDE]:
        if component == 'camera':
            camera_config = {
                CONF_NAME: device_config[CONF_NAME],
                CONF_HOST: device_config[CONF_HOST],
                CONF_PORT: device_config[CONF_PORT],
                CONF_USERNAME: device_config[CONF_USERNAME],
                CONF_PASSWORD: device_config[CONF_PASSWORD]
            }
            discovery.load_platform(
                hass, component, DOMAIN, camera_config, config)

    if event_types:
        hass.add_job(device.start)
    return True
