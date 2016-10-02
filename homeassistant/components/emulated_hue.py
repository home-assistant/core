"""
Support for local control of entities by emulating the Phillips Hue bridge.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emulated_hue/
"""
import threading
import socket
import logging
import json
import os
import select

import voluptuous as vol

from homeassistant import util, core
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    STATE_ON, HTTP_BAD_REQUEST
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_SUPPORTED_FEATURES, SUPPORT_BRIGHTNESS
)
from homeassistant.components.http import (
    HomeAssistantView, HomeAssistantWSGI
)
# pylint: disable=unused-import
from homeassistant.components.http import REQUIREMENTS   # noqa
import homeassistant.helpers.config_validation as cv

DOMAIN = 'emulated_hue'

_LOGGER = logging.getLogger(__name__)

CONF_HOST_IP = 'host_ip'
CONF_LISTEN_PORT = 'listen_port'
CONF_OFF_MAPS_TO_ON_DOMAINS = 'off_maps_to_on_domains'
CONF_EXPOSE_BY_DEFAULT = 'expose_by_default'
CONF_EXPOSED_DOMAINS = 'exposed_domains'

ATTR_EMULATED_HUE = 'emulated_hue'
ATTR_EMULATED_HUE_NAME = 'emulated_hue_name'

DEFAULT_LISTEN_PORT = 8300
DEFAULT_OFF_MAPS_TO_ON_DOMAINS = ['script', 'scene']
DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    'switch', 'light', 'group', 'input_boolean', 'media_player', 'fan'
]

HUE_API_STATE_ON = 'on'
HUE_API_STATE_BRI = 'bri'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST_IP): cv.string,
        vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Optional(CONF_OFF_MAPS_TO_ON_DOMAINS): cv.ensure_list,
        vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
        vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, yaml_config):
    """Activate the emulated_hue component."""
    config = Config(yaml_config)

    server = HomeAssistantWSGI(
        hass,
        development=False,
        server_host=config.host_ip_addr,
        server_port=config.listen_port,
        api_password=None,
        ssl_certificate=None,
        ssl_key=None,
        cors_origins=[],
        approved_ips=[]
    )

    server.register_view(DescriptionXmlView(hass, config))
    server.register_view(HueUsernameView(hass))
    server.register_view(HueLightsView(hass, config))

    upnp_listener = UPNPResponderThread(
        config.host_ip_addr, config.listen_port)

    def start_emulated_hue_bridge(event):
        """Start the emulated hue bridge."""
        server.start()
        upnp_listener.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_emulated_hue_bridge)

    def stop_emulated_hue_bridge(event):
        """Stop the emulated hue bridge."""
        upnp_listener.stop()
        server.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_emulated_hue_bridge)

    return True


# pylint: disable=too-few-public-methods
class Config(object):
    """Holds configuration variables for the emulated hue bridge."""

    def __init__(self, yaml_config):
        """Initialize the instance."""
        conf = yaml_config.get(DOMAIN, {})

        # Get the IP address that will be passed to the Echo during discovery
        self.host_ip_addr = conf.get(CONF_HOST_IP)
        if self.host_ip_addr is None:
            self.host_ip_addr = util.get_local_ip()
            _LOGGER.warning(
                "Listen IP address not specified, auto-detected address is %s",
                self.host_ip_addr)

        # Get the port that the Hue bridge will listen on
        self.listen_port = conf.get(CONF_LISTEN_PORT)
        if not isinstance(self.listen_port, int):
            self.listen_port = DEFAULT_LISTEN_PORT
            _LOGGER.warning(
                "Listen port not specified, defaulting to %s",
                self.listen_port)

        # Get domains that cause both "on" and "off" commands to map to "on"
        # This is primarily useful for things like scenes or scripts, which
        # don't really have a concept of being off
        self.off_maps_to_on_domains = conf.get(CONF_OFF_MAPS_TO_ON_DOMAINS)
        if not isinstance(self.off_maps_to_on_domains, list):
            self.off_maps_to_on_domains = DEFAULT_OFF_MAPS_TO_ON_DOMAINS

        # Get whether or not entities should be exposed by default, or if only
        # explicitly marked ones will be exposed
        self.expose_by_default = conf.get(
            CONF_EXPOSE_BY_DEFAULT, DEFAULT_EXPOSE_BY_DEFAULT)

        # Get domains that are exposed by default when expose_by_default is
        # True
        self.exposed_domains = conf.get(
            CONF_EXPOSED_DOMAINS, DEFAULT_EXPOSED_DOMAINS)


class DescriptionXmlView(HomeAssistantView):
    """Handles requests for the description.xml file."""

    url = '/description.xml'
    name = 'description:xml'
    requires_auth = False

    def __init__(self, hass, config):
        """Initialize the instance of the view."""
        super().__init__(hass)
        self.config = config

    def get(self, request):
        """Handle a GET request."""
        xml_template = """<?xml version="1.0" encoding="UTF-8" ?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>http://{0}:{1}/</URLBase>
<device>
<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
<friendlyName>HASS Bridge ({0})</friendlyName>
<manufacturer>Royal Philips Electronics</manufacturer>
<manufacturerURL>http://www.philips.com</manufacturerURL>
<modelDescription>Philips hue Personal Wireless Lighting</modelDescription>
<modelName>Philips hue bridge 2015</modelName>
<modelNumber>BSB002</modelNumber>
<modelURL>http://www.meethue.com</modelURL>
<serialNumber>1234</serialNumber>
<UDN>uuid:2f402f80-da50-11e1-9b23-001788255acc</UDN>
</device>
</root>
"""

        resp_text = xml_template.format(
            self.config.host_ip_addr, self.config.listen_port)

        return self.Response(resp_text, mimetype='text/xml')


class HueUsernameView(HomeAssistantView):
    """Handle requests to create a username for the emulated hue bridge."""

    url = '/api'
    name = 'hue:api'
    extra_urls = ['/api/']
    requires_auth = False

    def __init__(self, hass):
        """Initialize the instance of the view."""
        super().__init__(hass)

    def post(self, request):
        """Handle a POST request."""
        data = request.json

        if 'devicetype' not in data:
            return self.json_message('devicetype not specified',
                                     HTTP_BAD_REQUEST)

        return self.json([{'success': {'username': '12345678901234567890'}}])


class HueLightsView(HomeAssistantView):
    """Handle requests for getting and setting info about entities."""

    url = '/api/<username>/lights'
    name = 'api:username:lights'
    extra_urls = ['/api/<username>/lights/<entity_id>',
                  '/api/<username>/lights/<entity_id>/state']
    requires_auth = False

    def __init__(self, hass, config):
        """Initialize the instance of the view."""
        super().__init__(hass)
        self.config = config
        self.cached_states = {}

    def get(self, request, username, entity_id=None):
        """Handle a GET request."""
        if entity_id is None:
            return self.get_lights_list()

        if not request.base_url.endswith('state'):
            return self.get_light_state(entity_id)

        return self.Response("Method not allowed", status=405)

    def put(self, request, username, entity_id=None):
        """Handle a PUT request."""
        if not request.base_url.endswith('state'):
            return self.Response("Method not allowed", status=405)

        content_type = request.environ.get('CONTENT_TYPE', '')
        if content_type == 'application/x-www-form-urlencoded':
            # Alexa sends JSON data with a form data content type, for
            # whatever reason, and Werkzeug parses form data automatically,
            # so we need to do some gymnastics to get the data we need
            json_data = None

            for key in request.form:
                try:
                    json_data = json.loads(key)
                    break
                except ValueError:
                    # Try the next key?
                    pass

            if json_data is None:
                return self.Response("Bad request", status=400)
        else:
            json_data = request.json

        return self.put_light_state(json_data, entity_id)

    def get_lights_list(self):
        """Process a request to get the list of available lights."""
        json_response = {}

        for entity in self.hass.states.all():
            if self.is_entity_exposed(entity):
                json_response[entity.entity_id] = entity_to_json(entity)

        return self.json(json_response)

    def get_light_state(self, entity_id):
        """Process a request to get the state of an individual light."""
        entity = self.hass.states.get(entity_id)
        if entity is None or not self.is_entity_exposed(entity):
            return self.Response("Entity not found", status=404)

        cached_state = self.cached_states.get(entity_id, None)

        if cached_state is None:
            final_state = entity.state == STATE_ON
            final_brightness = entity.attributes.get(
                ATTR_BRIGHTNESS, 255 if final_state else 0)
        else:
            final_state, final_brightness = cached_state

        json_response = entity_to_json(entity, final_state, final_brightness)

        return self.json(json_response)

    def put_light_state(self, request_json, entity_id):
        """Process a request to set the state of an individual light."""
        config = self.config

        # Retrieve the entity from the state machine
        entity = self.hass.states.get(entity_id)
        if entity is None:
            return self.Response("Entity not found", status=404)

        if not self.is_entity_exposed(entity):
            return self.Response("Entity not found", status=404)

        # Parse the request into requested "on" status and brightness
        parsed = parse_hue_api_put_light_body(request_json, entity)

        if parsed is None:
            return self.Response("Bad request", status=400)

        result, brightness = parsed

        # Convert the resulting "on" status into the service we need to call
        service = SERVICE_TURN_ON if result else SERVICE_TURN_OFF

        # Construct what we need to send to the service
        data = {ATTR_ENTITY_ID: entity_id}

        if brightness is not None:
            data[ATTR_BRIGHTNESS] = brightness

        if entity.domain.lower() in config.off_maps_to_on_domains:
            # Map the off command to on
            service = SERVICE_TURN_ON

            # Caching is required because things like scripts and scenes won't
            # report as "off" to Alexa if an "off" command is received, because
            # they'll map to "on". Thus, instead of reporting its actual
            # status, we report what Alexa will want to see, which is the same
            # as the actual requested command.
            self.cached_states[entity_id] = (result, brightness)

        # Perform the requested action
        self.hass.services.call(core.DOMAIN, service, data, blocking=True)

        json_response = \
            [create_hue_success_response(entity_id, HUE_API_STATE_ON, result)]

        if brightness is not None:
            json_response.append(create_hue_success_response(
                entity_id, HUE_API_STATE_BRI, brightness))

        return self.json(json_response)

    def is_entity_exposed(self, entity):
        """Determine if an entity should be exposed on the emulated bridge."""
        config = self.config

        if entity.attributes.get('view') is not None:
            # Ignore entities that are views
            return False

        domain = entity.domain.lower()
        explicit_expose = entity.attributes.get(ATTR_EMULATED_HUE, None)

        domain_exposed_by_default = \
            config.expose_by_default and domain in config.exposed_domains

        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = \
            domain_exposed_by_default and explicit_expose is not False

        return is_default_exposed or explicit_expose


def parse_hue_api_put_light_body(request_json, entity):
    """Parse the body of a request to change the state of a light."""
    if HUE_API_STATE_ON in request_json:
        if not isinstance(request_json[HUE_API_STATE_ON], bool):
            return None

        if request_json['on']:
            # Echo requested device be turned on
            brightness = None
            report_brightness = False
            result = True
        else:
            # Echo requested device be turned off
            brightness = None
            report_brightness = False
            result = False

    if HUE_API_STATE_BRI in request_json:
        # Make sure the entity actually supports brightness
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if (entity_features & SUPPORT_BRIGHTNESS) == SUPPORT_BRIGHTNESS:
            try:
                # Clamp brightness from 0 to 255
                brightness = \
                    max(0, min(int(request_json[HUE_API_STATE_BRI]), 255))
            except ValueError:
                return None

            report_brightness = True
            result = (brightness > 0)

    return (result, brightness) if report_brightness else (result, None)


def entity_to_json(entity, is_on=None, brightness=None):
    """Convert an entity to its Hue bridge JSON representation."""
    if is_on is None:
        is_on = entity.state == STATE_ON

    if brightness is None:
        brightness = 255 if is_on else 0

    name = entity.attributes.get(
        ATTR_EMULATED_HUE_NAME, entity.attributes[ATTR_FRIENDLY_NAME])

    return {
        'state':
        {
            HUE_API_STATE_ON: is_on,
            HUE_API_STATE_BRI: brightness,
            'reachable': True
        },
        'type': 'Dimmable light',
        'name': name,
        'modelid': 'HASS123',
        'uniqueid': entity.entity_id,
        'swversion': '123'
    }


def create_hue_success_response(entity_id, attr, value):
    """Create a success response for an attribute set on a light."""
    success_key = '/lights/{}/state/{}'.format(entity_id, attr)
    return {'success': {success_key: value}}


class UPNPResponderThread(threading.Thread):
    """Handle responding to UPNP/SSDP discovery requests."""

    _interrupted = False

    def __init__(self, host_ip_addr, listen_port):
        """Initialize the class."""
        threading.Thread.__init__(self)

        self.host_ip_addr = host_ip_addr
        self.listen_port = listen_port

        # Note that the double newline at the end of
        # this string is required per the SSDP spec
        resp_template = """HTTP/1.1 200 OK
CACHE-CONTROL: max-age=60
EXT:
LOCATION: http://{0}:{1}/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/0.1
ST: urn:schemas-upnp-org:device:basic:1
USN: uuid:Socket-1_0-221438K0100073::urn:schemas-upnp-org:device:basic:1

"""

        self.upnp_response = resp_template.format(host_ip_addr, listen_port) \
                                          .replace("\n", "\r\n") \
                                          .encode('utf-8')

        # Set up a pipe for signaling to the receiver that it's time to
        # shutdown. Essentially, we place the SSDP socket into nonblocking
        # mode and use select() to wait for data to arrive on either the SSDP
        # socket or the pipe. If data arrives on either one, select() returns
        # and tells us which filenos have data ready to read.
        #
        # When we want to stop the responder, we write data to the pipe, which
        # causes the select() to return and indicate that said pipe has data
        # ready to be read, which indicates to us that the responder needs to
        # be shutdown.
        self._interrupted_read_pipe, self._interrupted_write_pipe = os.pipe()

    def run(self):
        """Run the server."""
        # Listen for UDP port 1900 packets sent to SSDP multicast address
        ssdp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ssdp_socket.setblocking(False)

        # Required for receiving multicast
        ssdp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        ssdp_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_MULTICAST_IF,
            socket.inet_aton(self.host_ip_addr))

        ssdp_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton("239.255.255.250") +
            socket.inet_aton(self.host_ip_addr))

        ssdp_socket.bind(("239.255.255.250", 1900))

        while True:
            if self._interrupted:
                clean_socket_close(ssdp_socket)
                return

            try:
                read, _, _ = select.select(
                    [self._interrupted_read_pipe, ssdp_socket], [],
                    [ssdp_socket])

                if self._interrupted_read_pipe in read:
                    # Implies self._interrupted is True
                    clean_socket_close(ssdp_socket)
                    return
                elif ssdp_socket in read:
                    data, addr = ssdp_socket.recvfrom(1024)
                else:
                    continue
            except socket.error as ex:
                if self._interrupted:
                    clean_socket_close(ssdp_socket)
                    return

                _LOGGER.error("UPNP Responder socket exception occured: %s",
                              ex.__str__)

            if "M-SEARCH" in data.decode('utf-8'):
                # SSDP M-SEARCH method received, respond to it with our info
                resp_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM)

                resp_socket.sendto(self.upnp_response, addr)
                resp_socket.close()

    def stop(self):
        """Stop the server."""
        # Request for server
        self._interrupted = True
        os.write(self._interrupted_write_pipe, bytes([0]))
        self.join()


def clean_socket_close(sock):
    """Close a socket connection and logs its closure."""
    _LOGGER.info("UPNP responder shutting down.")

    sock.close()
