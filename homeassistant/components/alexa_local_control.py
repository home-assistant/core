"""
Support for local control of entities through Alexa.

A sample configuration entry is given below:

    alexa_local_control:
      host_ip: 192.168.1.186
      listen_port: 8300
      off_maps_to_on_domains:
        - script
        - scene
      expose_by_default: true
      exposed_domains:
        - light

    homeassistant:
      customize:
        light.bedroom_light:
          # Don't allow light.bedroom_light to be controlled by Alexa
          echo: false
        light.office_light:
          # Address light.office_light as "back office light"
          echo_friendly_name: "back office light"

- host_ip defines the IP address that your Home Assistant installation is
  running on. If you do not specify this option, the component will attempt to
  determine the IP address on its own.

- listen_port defines the port the Hue bridge API web server will run on. If
  not specified, this defaults to 8300.

- off_maps_to_on_domains specifies the domains that maps an "off" command to
  an "on" command. For example, if "script" is included in the list, and you
  ask Alexa to "turn off the water plants script," the command will be handled
  as if you asked her to turn on the script. If not specified, this defaults
  to the following list:
      - 'script'
      - 'scene'

- expose_by_default specifies whether or not entities should be exposed via the
  bridge by default instead of explicitly (see the 'echo' attribute later on).
  If not specified, this defaults to true.

- exposed_domains defines the domains that are exposed by default if
  expose_by_default is set to true. If not specified, this defaults to the
  following list:
      - 'switch'
      - 'light'
      - 'script'
      - 'scene'
      - 'group'
      - 'input_boolean'
      - 'media_player'

The following are attributes that can be applied in the customize section:

- echo specifies whether or not the entity should be discoverable by Alexa. The
  default for this attribute is controlled with the expose_by_default config
  option.

- echo_friendly_name specifies the name that Alexa will know the entity as. The
  default for this is the entity's friendly name.

Much of this code is based on work done by Bruce Locke on his ha-local-echo
project, located at "https://github.com/blocke/ha-local-echo", originally
released under the MIT License. The license is reproduced below:

The MIT License (MIT)

Copyright (c) 2016 Bruce Locke

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import threading
import socket
import logging
import json

import voluptuous as vol

from homeassistant import util, core
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    EVENT_HOMEASSISTANT_START
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_SUPPORTED_FEATURES, SUPPORT_BRIGHTNESS
)
import homeassistant.helpers.config_validation as cv

DOMAIN = "alexa_local_control"

REQUIREMENTS = ['Flask==0.11.1']

_LOGGER = logging.getLogger(__name__)

CONF_HOST_IP = 'host_ip'
CONF_LISTEN_PORT = 'listen_port'
CONF_OFF_MAPS_TO_ON_DOMAINS = 'off_maps_to_on_domains'
CONF_EXPOSE_BY_DEFAULT = 'expose_by_default'
CONF_EXPOSED_DOMAINS = 'exposed_domains'

ATTR_ECHO = 'echo'
ATTR_ECHO_FRIENDLY_NAME = 'echo_friendly_name'

DEFAULT_LISTEN_PORT = 8300
DEFAULT_OFF_MAPS_TO_ON_DOMAINS = ['script', 'scene']
DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    'switch', 'light', 'script', 'scene', 'group', 'input_boolean',
    'media_player'
]

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


def setup(hass, config):
    """Activate the alexa_local_control component."""
    from flask import Flask

    app = Flask(__name__)
    app.url_map.strict_slashes = False

    view = HueBridgeView(hass, config)
    view.set_up_routes(app)

    def start_listener(event):
        """Start listening for UPNP/SSDP requests."""
        upnp_listener = UPNPResponderThread(
            view.host_ip_addr, view.listen_port)
        upnp_listener.start()

    def start_web_server():
        """Start the Hue bridge API web server."""
        from cherrypy import wsgiserver

        dispatcher = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        server = wsgiserver.CherryPyWSGIServer(
            ('0.0.0.0', view.listen_port), dispatcher)

        server.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_listener)
    threading.Thread(target=start_web_server, daemon=True, name=DOMAIN).start()

    return True


class HueBridgeView(object):
    """An instance of an emulated Hue bridge."""

    def __init__(self, hass_instance, config):
        """Initialize the instance."""
        self.hass = hass_instance
        self.cached_states = {}

        self.fill_with_config(config)

    def fill_with_config(self, config):
        """Fill the instance with data from the ocnfiguration file."""
        conf = config.get(DOMAIN, {})

        # Get the IP address that will be passed to the Echo during discovery
        self.host_ip_addr = conf.get(CONF_HOST_IP)
        if self.host_ip_addr is None:
            self.host_ip_addr = util.get_local_ip()
            _LOGGER.warning(
                "Listen IP address not specified, auto-detected address is %s",
                self.host_ip_addr)

        # Get the port that the Hue bridge will listen on
        self.listen_port = conf.get(CONF_LISTEN_PORT)
        if not isinstance(type(self.listen_port), int):
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
        self.expose_by_default = conf.get(CONF_EXPOSE_BY_DEFAULT)
        if not isinstance(type(self.expose_by_default), bool):
            self.expose_by_default = DEFAULT_EXPOSE_BY_DEFAULT

        # Get domains that are exposed by default when expose_by_default is
        # True
        self.exposed_domains = conf.get(CONF_EXPOSED_DOMAINS)
        if not isinstance(self.exposed_domains, list):
            self.exposed_domains = DEFAULT_EXPOSED_DOMAINS

    def set_up_routes(self, app):
        """Set up Flask routes."""
        app.route('/description.xml', methods=['GET'])(
            self.description_xml)

        app.route('/api/<token>/lights', methods=['GET'])(
            self.hue_api_lights)
        app.route('/api/<token>/lights/', methods=['GET'])(
            self.hue_api_lights)

        app.route('/api/<token>/lights/<entity_id>/state', methods=['PUT'])(
            self.hue_api_put_light)

        app.route('/api/<token>/lights/<entity_id>', methods=['GET'])(
            self.hue_api_individual_light)

        app.route('/api', methods=['POST'])(
            self.hue_api_create_user)

    def description_xml(self):
        """Handle requests for the bridge's description.xml."""
        from flask import Response

        xml_template = """<?xml version="1.0" encoding="UTF-8" ?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>http://{0}:{1}/</URLBase>
<device>
<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
<friendlyName>HA-Echo ({0})</friendlyName>
<manufacturer>Royal Philips Electronics</manufacturer>
<manufacturerURL>http://www.philips.com</manufacturerURL>
<modelDescription>Philips hue Personal Wireless Lighting</modelDescription>
<modelName>Philips hue bridge 2015</modelName>
<modelNumber>BSB002</modelNumber>
<modelURL>http://www.meethue.com</modelURL>
<serialNumber>1234</serialNumber>
<UDN>uuid:2f402f80-da50-11e1-9b23-001788255acc</UDN>
<presentationURL>index.html</presentationURL>
<iconList>
<icon>
<mimetype>image/png</mimetype>
<height>48</height>
<width>48</width>
<depth>24</depth>
<url>hue_logo_0.png</url>
</icon>
<icon>
<mimetype>image/png</mimetype>
<height>120</height>
<width>120</width>
<depth>24</depth>
<url>hue_logo_3.png</url>
</icon>
</iconList>
</device>
</root>
"""

        resp_text = xml_template.format(
            self.host_ip_addr, self.listen_port)

        return Response(resp_text, mimetype='text/xml')

    def hue_api_lights(self, token):
        """Handle requests for lights accessible to users of the bridge API."""
        from flask import Response

        json_response = {}

        for entity in self.hass.states.all():
            if ('view' in entity.attributes) and (entity.attributes['view']):
                # Ignore entities that are views
                continue

            domain = entity.domain.lower()
            explicit_expose = entity.attributes.get(ATTR_ECHO, False)

            domain_exposed_by_default = \
                self.expose_by_default and domain in self.exposed_domains

            if domain_exposed_by_default or explicit_expose:
                json_response[entity.entity_id] = entity_to_json(entity)

        return Response(json.dumps(json_response), mimetype='application/json')

    def hue_api_put_light(self, token, entity_id):
        """Handle requests to change the state of a light."""
        from flask import Response, abort, request

        # Retrieve the entity from the state machine
        entity = self.hass.states.get(entity_id)
        if entity is None:
            abort(404)

        # Parse the request into requested "on" status and brightness
        parsed = parse_hue_api_put_light_body(
            request.get_json(force=True), entity)

        if parsed is None:
            abort(500)

        result, brightness = parsed

        # Convert the resulting "on" status into the service we need to call
        service = SERVICE_TURN_ON if result else SERVICE_TURN_OFF

        # Construct what we need to send to the service
        data = {ATTR_ENTITY_ID: entity_id}

        if brightness is not None:
            data[ATTR_BRIGHTNESS] = brightness

        if entity.domain.lower() in self.off_maps_to_on_domains:
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

        response = [create_hue_success_response(entity_id, 'on', result)]

        if brightness is not None:
            response.append(
                create_hue_success_response(entity_id, 'bri', brightness))

        return Response(
            json.dumps(response), mimetype='application/json', status=200)

    def hue_api_individual_light(self, token, entity_id):
        """Handle requests for the status of an individual light."""
        from flask import Response, abort

        entity = self.hass.states.get(entity_id)
        if entity is None:
            abort(404)

        cached_state = self.cached_states.get(entity_id, None)

        if cached_state is None:
            final_state = entity.state == 'on'
            final_brightness = entity.attributes.get(
                ATTR_BRIGHTNESS, 255 if final_state else 0)
        else:
            final_state, final_brightness = cached_state

        json_response = entity_to_json(entity, final_state, final_brightness)

        return Response(json.dumps(json_response), mimetype='application/json')

    # pylint: disable=no-self-use
    def hue_api_create_user(self):
        """Handle requests to create a new user for the local bridge."""
        from flask import Response, request, abort

        request_json = request.get_json(force=True)

        if 'devicetype' not in request_json:
            abort(500)

        json_response = [{'success': {'username': '12345678901234567890'}}]

        return Response(json.dumps(json_response), mimetype='application/json')


def parse_hue_api_put_light_body(request_json, entity):
    """Parse the body of a request to change the state of a light."""
    if 'on' in request_json:
        if not isinstance(request_json['on'], bool):
            return None

        if request_json['on']:
            # Echo requested device be turned on
            brightness = 100
            report_brightness = False
            result = True
        else:
            # Echo requested device be turned off
            brightness = 0
            report_brightness = False
            result = False

    if 'bri' in request_json:
        # Make sure the entity actually supports brightness
        entity_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if (entity_features & SUPPORT_BRIGHTNESS) == SUPPORT_BRIGHTNESS:
            try:
                # Clamp brightness from 0 to 255
                brightness = max(0, min(int(request_json['bri']), 255))
            except ValueError:
                return None

            report_brightness = True
            result = True if brightness > 0 else False

    return (result, brightness) if report_brightness else (result, None)


def entity_to_json(entity, is_on=None, brightness=None):
    """Convert an entity to its JSON representation."""
    if is_on is None:
        is_on = entity.state == "on"

    if brightness is None:
        brightness = 255 if is_on else 0

    name = entity.attributes.get(
        ATTR_ECHO_FRIENDLY_NAME, entity.attributes['friendly_name'])

    return {
        'state':
        {
            'on': is_on,
            'bri': brightness,
            'hue': 0,
            'sat': 0,
            'effect': 'none',
            'ct': 0,
            'alert': 'none',
            'reachable': True
        },
        'type': 'Dimmable light',
        'name': name,
        'modelid': 'LWB004',
        'manufacturername': 'Philips',
        'uniqueid': entity.entity_id,
        'swversion': '66012040'}


def create_hue_success_response(entity_id, attr, value):
    """Create a success response for an attribute set on a light."""
    success_key = '/lights/{}/state/{}'.format(entity_id, attr)
    return {'success': {success_key: value}}


class UPNPResponderThread(threading.Thread):
    """Handle responding to UPNP/SSDP discovery requests."""

    stop_thread = False

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

    def run(self):
        """Run the server."""
        # Listen for UDP port 1900 packets sent to SSDP multicast address
        ssdpmc_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Required for receiving multicast
        ssdpmc_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        ssdpmc_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_MULTICAST_IF,
            socket.inet_aton(self.host_ip_addr))

        ssdpmc_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton("239.255.255.250") +
            socket.inet_aton(self.host_ip_addr))

        ssdpmc_socket.bind(("239.255.255.250", 1900))

        while True:
            try:
                data, addr = ssdpmc_socket.recvfrom(1024)
            except socket.error as ex:
                if self.stop_thread:
                    _LOGGER.error(("UPNP Reponder Thread closing socket and "
                                   "shutting down..."))
                    ssdpmc_socket.close()
                    return
                _LOGGER.error(
                    "UPNP Responder socket.error exception occured: %s",
                    ex.__str__)

            if "M-SEARCH" in data.decode('utf-8'):
                # SSDP M-SEARCH method received, respond to it with our info
                ssdpout_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM)

                ssdpout_socket.sendto(self.upnp_response, addr)
                ssdpout_socket.close()

    def stop(self):
        """Stop the server."""
        # Request for thread to stop
        self.stop_thread = True
