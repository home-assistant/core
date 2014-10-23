"""
homeassistant.components.httpinterface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides an API and a HTTP interface for debug purposes.

By default it will run on port 8123.

All API calls have to be accompanied by an 'api_password' parameter and will
return JSON. If successful calls will return status code 200 or 201.

Other status codes that can occur are:
 - 400 (Bad Request)
 - 401 (Unauthorized)
 - 404 (Not Found)
 - 405 (Method not allowed)

The api supports the following actions:

/api - GET
Returns message if API is up and running.
Example result:
{
  "message": "API running."
}

/api/states - GET
Returns a list of entities for which a state is available
Example result:
[
    { .. state object .. },
    { .. state object .. }
]

/api/states/<entity_id> - GET
Returns the current state from an entity
Example result:
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013",
        "next_setting": "18:00:31 29-10-2013"
    },
    "entity_id": "weather.sun",
    "last_changed": "23:24:33 28-10-2013",
    "state": "below_horizon"
}

/api/states/<entity_id> - POST
Updates the current state of an entity. Returns status code 201 if successful
with location header of updated resource and as body the new state.
parameter: new_state - string
optional parameter: attributes - JSON encoded object
Example result:
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013",
        "next_setting": "18:00:31 29-10-2013"
    },
    "entity_id": "weather.sun",
    "last_changed": "23:24:33 28-10-2013",
    "state": "below_horizon"
}

/api/events/<event_type> - POST
Fires an event with event_type
optional parameter: event_data - JSON encoded object
Example result:
{
    "message": "Event download_file fired."
}

"""

import json
import threading
import logging
import re
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

import homeassistant as ha
import homeassistant.remote as rem
import homeassistant.util as util
from homeassistant.components import (STATE_ON, STATE_OFF,
                                      SERVICE_TURN_ON, SERVICE_TURN_OFF)
DOMAIN = "http"
DEPENDENCIES = []

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422

URL_ROOT = "/"

URL_STATIC = "/static/{}"

DOMAIN_ICONS = {
    "sun": "glyphicon-asterisk",
    "group": "glyphicon-th-large",
    "charging": "glyphicon-flash",
    "light": "glyphicon-hdd",
    "wemo": "glyphicon-hdd",
    "device_tracker": "glyphicon-phone",
    "chromecast": "glyphicon-picture",
    "process": "glyphicon-barcode",
    "browser": "glyphicon-globe",
    "homeassistant": "glyphicon-home",
    "downloader": "glyphicon-download-alt"
}

CONF_API_PASSWORD = "api_password"
CONF_SERVER_HOST = "server_host"
CONF_SERVER_PORT = "server_port"


def _get_domain_icon(domain):
    """ Returns HTML that shows domain icon. """
    return "<span class='glyphicon {}'></span>".format(
        DOMAIN_ICONS.get(domain, ""))


def setup(hass, config):
    """ Sets up the HTTP API and debug interface. """

    if not util.validate_config(config, {DOMAIN: [CONF_API_PASSWORD]},
                                logging.getLogger(__name__)):
        return False

    api_password = config[DOMAIN]['api_password']

    # If no server host is given, accept all incoming requests
    server_host = config[DOMAIN].get(CONF_SERVER_HOST, '0.0.0.0')

    server_port = config[DOMAIN].get(CONF_SERVER_PORT, rem.SERVER_PORT)

    server = HomeAssistantHTTPServer((server_host, server_port),
                                     RequestHandler, hass, api_password)

    hass.listen_once_event(
        ha.EVENT_HOMEASSISTANT_START,
        lambda event:
        threading.Thread(target=server.start, daemon=True).start())

    # If no local api set, set one with known information
    if isinstance(hass, rem.HomeAssistant) and hass.local_api is None:
        hass.local_api = \
            rem.API(util.get_local_ip(), api_password, server_port)

    return True


class HomeAssistantHTTPServer(ThreadingMixIn, HTTPServer):
    """ Handle HTTP requests in a threaded fashion. """

    def __init__(self, server_address, RequestHandlerClass,
                 hass, api_password):
        super().__init__(server_address, RequestHandlerClass)

        self.hass = hass
        self.api_password = api_password
        self.server_address = server_address
        self.logger = logging.getLogger(__name__)

        # To store flash messages between sessions
        self.flash_message = None

        # We will lazy init this one if needed
        self.event_forwarder = None

    def start(self):
        """ Starts the server. """
        self.logger.info(
            "Web interface starting at http://{}:{}".format(
                *self.server_address))

        self.serve_forever()


# pylint: disable=too-many-public-methods
class RequestHandler(BaseHTTPRequestHandler):
    """ Handles incoming HTTP requests """

    PATHS = [  # debug interface
        ('GET', URL_ROOT, '_handle_get_root'),
        ('POST', URL_ROOT, '_handle_get_root'),

        # /api - for validation purposes
        ('GET', rem.URL_API, '_handle_get_api'),

        # /states
        ('GET', rem.URL_API_STATES, '_handle_get_api_states'),
        ('GET',
         re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
         '_handle_get_api_states_entity'),
        ('POST',
         re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
         '_handle_post_state_entity'),
        ('PUT',
         re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
         '_handle_post_state_entity'),

        # /events
        ('GET', rem.URL_API_EVENTS, '_handle_get_api_events'),
        ('POST',
         re.compile(r'/api/events/(?P<event_type>[a-zA-Z\._0-9]+)'),
         '_handle_api_post_events_event'),

        # /services
        ('GET', rem.URL_API_SERVICES, '_handle_get_api_services'),
        ('POST',
         re.compile((r'/api/services/'
                     r'(?P<domain>[a-zA-Z\._0-9]+)/'
                     r'(?P<service>[a-zA-Z\._0-9]+)')),
         '_handle_post_api_services_domain_service'),

        # /event_forwarding
        ('POST', rem.URL_API_EVENT_FORWARD, '_handle_post_api_event_forward'),
        ('DELETE', rem.URL_API_EVENT_FORWARD,
         '_handle_delete_api_event_forward'),

        # Statis files
        ('GET', re.compile(r'/static/(?P<file>[a-zA-Z\._\-0-9/]+)'),
         '_handle_get_static')
    ]

    use_json = False

    def _handle_request(self, method):  # pylint: disable=too-many-branches
        """ Does some common checks and calls appropriate method. """
        url = urlparse(self.path)

        if url.path.startswith('/api/'):
            self.use_json = True

        # Read query input
        data = parse_qs(url.query)

        # parse_qs gives a list for each value, take the latest element
        for key in data:
            data[key] = data[key][-1]

        # Did we get post input ?
        content_length = int(self.headers.get('Content-Length', 0))

        if content_length:
            body_content = self.rfile.read(content_length).decode("UTF-8")

            if self.use_json:
                try:
                    data.update(json.loads(body_content))
                except ValueError:
                    self.server.logger.exception(
                        "Exception parsing JSON: {}".format(body_content))

                    self.send_response(HTTP_UNPROCESSABLE_ENTITY)
                    return
            else:
                data.update({key: value[-1] for key, value in
                             parse_qs(body_content).items()})

        api_password = self.headers.get(rem.AUTH_HEADER)

        if not api_password and 'api_password' in data:
            api_password = data['api_password']

        if '_METHOD' in data:
            method = data.pop('_METHOD')

        # Var to keep track if we found a path that matched a handler but
        # the method was different
        path_matched_but_not_method = False

        # Var to hold the handler for this path and method if found
        handle_request_method = False

        # Check every handler to find matching result
        for t_method, t_path, t_handler in RequestHandler.PATHS:

            # we either do string-comparison or regular expression matching
            # pylint: disable=maybe-no-member
            if isinstance(t_path, str):
                path_match = url.path == t_path
            else:
                path_match = t_path.match(url.path)

            if path_match and method == t_method:
                # Call the method
                handle_request_method = getattr(self, t_handler)
                break

            elif path_match:
                path_matched_but_not_method = True

        # Did we find a handler for the incoming request?
        if handle_request_method:

            # Do not enforce api password for static files
            if handle_request_method == self._handle_get_static or \
               self._verify_api_password(api_password):

                handle_request_method(path_match, data)

        elif path_matched_but_not_method:
            self.send_response(HTTP_METHOD_NOT_ALLOWED)

        else:
            self.send_response(HTTP_NOT_FOUND)

    def do_GET(self):  # pylint: disable=invalid-name
        """ GET request handler. """
        self._handle_request('GET')

    def do_POST(self):  # pylint: disable=invalid-name
        """ POST request handler. """
        self._handle_request('POST')

    def do_PUT(self):  # pylint: disable=invalid-name
        """ PUT request handler. """
        self._handle_request('PUT')

    def do_DELETE(self):  # pylint: disable=invalid-name
        """ DELETE request handler. """
        self._handle_request('DELETE')

    def _verify_api_password(self, api_password):
        """ Helper method to verify the API password
            and take action if incorrect. """
        if api_password == self.server.api_password:
            return True

        elif self.use_json:
            self._message(
                "API password missing or incorrect.", HTTP_UNAUTHORIZED)

        else:
            self.send_response(HTTP_OK)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            self.wfile.write((
                "<html>"
                "<head><title>Home Assistant</title>"
                "<link rel='shortcut icon' href='/static/favicon.ico' />"
                "<link rel='icon' type='image/png' "
                "     href='/static/favicon-192x192.png' sizes='192x192'>"
                "</head>"
                "<body>"
                "<div>"
                "<form class='form-signin' action='{}' method='POST'>"

                "<input type='text' name='api_password' "
                "    placeholder='API Password for Home Assistant' "
                "    required autofocus>"

                "<button type='submit'>Enter</button>"

                "</form>"
                "</div>"
                "</body></html>").format(self.path).encode("UTF-8"))

        return False

    # pylint: disable=unused-argument
    def _handle_get_root(self, path_match, data):
        """ Renders the debug interface. """

        write = lambda txt: self.wfile.write((txt + "\n").encode("UTF-8"))

        self.send_response(HTTP_OK)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        # TODO let's be able to switch this based on env
        app_url = "build.htm" if False else "home-assistant-main.html"

        write(("<html>"
               "<head><title>Home Assistant</title>"
               "<meta name='mobile-web-app-capable' content='yes'>"
               "<link rel='shortcut icon' href='/static/favicon.ico' />"
               "<link rel='icon' type='image/png' "
               "     href='/static/favicon-192x192.png' sizes='192x192'>"
               "<script"
               "     src='/static/polymer/bower_components/"
               "platform/platform.js'></script>"
               "<link rel='import' href='/static/polymer/{}' />"
               "<meta name='viewport' content='width=device-width, "
               "      user-scalable=no, initial-scale=1.0, "
               "      minimum-scale=1.0, maximum-scale=1.0' />"
               "</head>"
               "<body unresolved fullbleed"
               "     style='background-color: #E5E5E5'>"
               "<home-assistant-main auth='{}'></home-assistant-main>"
               "</body></html>").format(app_url, self.server.api_password))

    # pylint: disable=unused-argument
    def _handle_get_api(self, path_match, data):
        """ Renders the debug interface. """
        self._message("API running.")

    # pylint: disable=unused-argument
    def _handle_get_api_states(self, path_match, data):
        """ Returns a dict containing all entity ids and their state. """
        self._write_json(self.server.hass.states.all())

    # pylint: disable=unused-argument
    def _handle_get_api_states_entity(self, path_match, data):
        """ Returns the state of a specific entity. """
        entity_id = path_match.group('entity_id')

        state = self.server.hass.states.get(entity_id)

        if state:
            self._write_json(state)
        else:
            self._message("State does not exist.", HTTP_NOT_FOUND)

    def _handle_post_state_entity(self, path_match, data):
        """ Handles updating the state of an entity.

        This handles the following paths:
        /api/states/<entity_id>
        """
        entity_id = path_match.group('entity_id')

        try:
            new_state = data['state']
        except KeyError:
            self._message("state not specified", HTTP_BAD_REQUEST)
            return

        attributes = data['attributes'] if 'attributes' in data else None

        is_new_state = self.server.hass.states.get(entity_id) is None

        # Write state
        self.server.hass.states.set(entity_id, new_state, attributes)

        # Return state if json, else redirect to main page
        if self.use_json:
            state = self.server.hass.states.get(entity_id)

            status_code = HTTP_CREATED if is_new_state else HTTP_OK

            self._write_json(state.as_dict(),
                             status_code=status_code,
                             location=
                             rem.URL_API_STATES_ENTITY.format(entity_id))
        else:
            self._message(
                "State of {} changed to {}".format(entity_id, new_state))

    def _handle_get_api_events(self, path_match, data):
        """ Handles getting overview of event listeners. """
        self._write_json([{"event": key, "listener_count": value}
                          for key, value
                          in self.server.hass.bus.listeners.items()])

    def _handle_api_post_events_event(self, path_match, event_data):
        """ Handles firing of an event.

        This handles the following paths:
        /api/events/<event_type>

        Events from /api are threated as remote events.
        """
        event_type = path_match.group('event_type')

        if event_data is not None and not isinstance(event_data, dict):
            self._message("event_data should be an object",
                          HTTP_UNPROCESSABLE_ENTITY)

        event_origin = ha.EventOrigin.remote

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        if event_type == ha.EVENT_STATE_CHANGED and event_data:
            for key in ('old_state', 'new_state'):
                state = ha.State.from_dict(event_data.get(key))

                if state:
                    event_data[key] = state

        self.server.hass.bus.fire(event_type, event_data, event_origin)

        self._message("Event {} fired.".format(event_type))

    def _handle_get_api_services(self, path_match, data):
        """ Handles getting overview of services. """
        self._write_json(
            [{"domain": key, "services": value}
             for key, value
             in self.server.hass.services.services.items()])

    # pylint: disable=invalid-name
    def _handle_post_api_services_domain_service(self, path_match, data):
        """ Handles calling a service.

        This handles the following paths:
        /api/services/<domain>/<service>
        """
        domain = path_match.group('domain')
        service = path_match.group('service')

        self.server.hass.call_service(domain, service, data)

        self._message("Service {}/{} called.".format(domain, service))

    # pylint: disable=invalid-name
    def _handle_post_api_event_forward(self, path_match, data):
        """ Handles adding an event forwarding target. """

        try:
            host = data['host']
            api_password = data['api_password']
        except KeyError:
            self._message("No host or api_password received.",
                          HTTP_BAD_REQUEST)
            return

        try:
            port = int(data['port']) if 'port' in data else None
        except ValueError:
            self._message(
                "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
            return

        if self.server.event_forwarder is None:
            self.server.event_forwarder = \
                rem.EventForwarder(self.server.hass)

        api = rem.API(host, api_password, port)

        self.server.event_forwarder.connect(api)

        self._message("Event forwarding setup.")

    def _handle_delete_api_event_forward(self, path_match, data):
        """ Handles deleting an event forwarding target. """

        try:
            host = data['host']
        except KeyError:
            self._message("No host received.",
                          HTTP_BAD_REQUEST)
            return

        try:
            port = int(data['port']) if 'port' in data else None
        except ValueError:
            self._message(
                "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
            return

        if self.server.event_forwarder is not None:
            api = rem.API(host, None, port)

            self.server.event_forwarder.disconnect(api)

        self._message("Event forwarding cancelled.")

    def _handle_get_static(self, path_match, data):
        """ Returns a static file. """
        req_file = util.sanitize_path(path_match.group('file'))

        path = os.path.join(os.path.dirname(__file__), 'www_static', req_file)

        if os.path.isfile(path):
            self.send_response(HTTP_OK)
            self.send_header("Cache-control", "public, max-age=3600")
            self.send_header("Expires",
                             self.date_time_string(time.time()+3600))

            self.end_headers()

            with open(path, 'rb') as inp:
                data = inp.read(1024)

                while data:
                    self.wfile.write(data)

                    data = inp.read(1024)

        else:
            self.send_response(HTTP_NOT_FOUND)
            self.end_headers()

    def _message(self, message, status_code=HTTP_OK):
        """ Helper method to return a message to the caller. """
        if self.use_json:
            self._write_json({'message': message}, status_code=status_code)
        elif status_code == HTTP_OK:
            self.server.flash_message = message
            self._redirect('/')
        else:
            self.send_error(status_code, message)

    def _redirect(self, location):
        """ Helper method to redirect caller. """
        self.send_response(HTTP_MOVED_PERMANENTLY)

        self.send_header(
            "Location", "{}?api_password={}".format(
                location, self.server.api_password))

        self.end_headers()

    def _write_json(self, data=None, status_code=HTTP_OK, location=None):
        """ Helper method to return JSON to the caller. """
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')

        if location:
            self.send_header('Location', location)

        self.end_headers()

        if data is not None:
            self.wfile.write(
                json.dumps(data, indent=4, sort_keys=True,
                           cls=rem.JSONEncoder).encode("UTF-8"))
