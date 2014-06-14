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
{
    "entity_ids": [
        "Paulus_Nexus_4",
        "weather.sun",
        "all_devices"
    ]
}

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

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422

URL_ROOT = "/"
URL_CHANGE_STATE = "/change_state"
URL_FIRE_EVENT = "/fire_event"
URL_CALL_SERVICE = "/call_service"

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


def _get_domain_icon(domain):
    return "<span class='glyphicon {}'></span>".format(
                DOMAIN_ICONS.get(domain, ""))


def setup(hass, api_password, server_port=None, server_host=None):
    """ Sets up the HTTP API and debug interface. """
    server_port = server_port or rem.SERVER_PORT

    # If no server host is given, accept all incoming requests
    server_host = server_host or '0.0.0.0'

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


class HomeAssistantHTTPServer(ThreadingMixIn, HTTPServer):
    """ Handle HTTP requests in a threaded fashion. """

    def __init__(self, server_address, RequestHandlerClass,
                 hass, api_password):
        super().__init__(server_address, RequestHandlerClass)

        self.hass = hass
        self.api_password = api_password
        self.logger = logging.getLogger(__name__)

        # To store flash messages between sessions
        self.flash_message = None

        # We will lazy init this one if needed
        self.event_forwarder = None

    def start(self):
        """ Starts the server. """
        self.logger.info("Starting")

        self.serve_forever()


# pylint: disable=too-many-public-methods
class RequestHandler(BaseHTTPRequestHandler):
    """ Handles incoming HTTP requests """

    PATHS = [  # debug interface
        ('GET', URL_ROOT, '_handle_get_root'),
        # These get compiled as RE because these methods are reused
        # by other urls that use url parameters
        ('POST', re.compile(URL_CHANGE_STATE), '_handle_change_state'),
        ('POST', re.compile(URL_FIRE_EVENT), '_handle_fire_event'),
        ('POST', re.compile(URL_CALL_SERVICE), '_handle_call_service'),

        # /api - for validation purposes
        ('GET', rem.URL_API, '_handle_get_api'),

        # /states
        ('GET', rem.URL_API_STATES, '_handle_get_api_states'),
        ('GET',
         re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
         '_handle_get_api_states_entity'),
        ('POST',
         re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
         '_handle_change_state'),

        # /events
        ('GET', rem.URL_API_EVENTS, '_handle_get_api_events'),
        ('POST',
         re.compile(r'/api/events/(?P<event_type>[a-zA-Z\._0-9]+)'),
         '_handle_fire_event'),

        # /services
        ('GET', rem.URL_API_SERVICES, '_handle_get_api_services'),
        ('POST',
         re.compile((r'/api/services/'
                     r'(?P<domain>[a-zA-Z\._0-9]+)/'
                     r'(?P<service>[a-zA-Z\._0-9]+)')),
         '_handle_call_service'),

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

        # Read query input
        data = parse_qs(url.query)

        # Did we get post input ?
        content_length = int(self.headers.get('Content-Length', 0))

        if content_length:
            data.update(parse_qs(self.rfile.read(
                content_length).decode("UTF-8")))

        try:
            api_password = data['api_password'][0]
        except KeyError:
            api_password = ''

        if '_METHOD' in data:
            method = data['_METHOD'][0]

        if url.path.startswith('/api/'):
            self.use_json = True

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
                "<link rel='stylesheet' type='text/css' "
                "     href='/static/style.css'>"
                "<link rel='icon' href='/static/favicon.ico' "
                "     type='image/x-icon' />"
                "</head>"
                "<body>"
                "<div class='container'>"
                "<form class='form-signin' action='{}' method='GET'>"

                "<input type='text' class='form-control' name='api_password' "
                "    placeholder='API Password for Home Assistant' "
                "    required autofocus>"

                "<button class='btn btn-lg btn-primary btn-block' "
                "    type='submit'>Enter</button>"

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

        write(("<html>"
               "<head><title>Home Assistant</title>"
               "<link rel='stylesheet' type='text/css' "
               "      href='/static/style.css'>"
               "<link rel='icon' href='/static/favicon.ico' "
               "      type='image/x-icon' />"
               "<script src='http://code.jquery.com/jquery-2.1.1.min.js'>"
               "      </script>"
               "<script type='text/javascript' src='/static/script.js'>"
               "      </script>"
               "</head>"
               "<body>"
               "<div class='container'>"
               "<div class='page-header'><h1>Home Assistant</h1></div>"))

        # Flash message support
        if self.server.flash_message:
            write(("<div class='row'><div class='col-xs-12'>"
                   "<div class='alert alert-success'>"
                   "{}</div></div></div>").format(self.server.flash_message))

            self.server.flash_message = None

        # Describe state machine:
        write(("<div class='row'>"
               "<div class='col-xs-12'>"
               "<div class='states panel panel-primary'>"
               "<div class='panel-heading'><h2 class='panel-title'>"
               "     States</h2></div>"
               "<form method='post' action='/change_state' "
               "     class='form-change-state'>"
               "<input type='hidden' name='api_password' value='{}'>"
               "<table class='table'><tr><th></th>"
               "<th>Entity ID</th><th>State</th>"
               "<th>Attributes</th><th>Last Changed</th>"
               "</tr>").format(self.server.api_password))

        for entity_id, state in \
            sorted(self.server.hass.states.all().items(),
                   key=lambda item: item[0].lower()):

            domain = util.split_entity_id(entity_id)[0]

            attributes = "<br>".join(
                "{}: {}".format(attr, val)
                for attr, val in state.attributes.items())

            write("<tr><td>{}</td><td>{}</td><td>{}".format(
                _get_domain_icon(domain), entity_id, state.state))

            if state.state == STATE_ON or state.state == STATE_OFF:
                if state.state == STATE_ON:
                    action = SERVICE_TURN_OFF
                else:
                    action = SERVICE_TURN_ON

                write(("<a class='glyphicon glyphicon-off pull-right' "
                       "data-service='homeassistant/{}' "
                       "data-entity_id='{}' data-service-autofire "
                       "href='#'></a>").format(action, state.entity_id))

            write("</td><td>{}</td><td>{}</td></tr>".format(
                  attributes, util.datetime_to_str(state.last_changed)))

        # Change state form
        write(("<tr><td></td><td><input name='entity_id' class='form-control' "
               "  placeholder='Entity ID'></td>"
               "<td><input name='new_state' class='form-control' "
               "  placeholder='New State'></td>"
               "<td><textarea rows='3' name='attributes' class='form-control' "
               "  placeholder='State Attributes (JSON, optional)'>"
               "</textarea></td>"
               "<td><button type='submit' class='btn btn-default'>"
               "Set State</button></td></tr>"

               "</table></form></div>"

               "</div></div>"))

        # Describe bus/services:
        write(("<div class='row'>"
               "<div class='col-xs-6'>"
               "<div class='services panel panel-primary'>"
               "<div class='panel-heading'><h2 class='panel-title'>"
               "     Services</h2></div>"
               "<table class='table'>"
               "<tr><th></th><th>Domain</th><th>Service</th></tr>"))

        for domain, services in sorted(
                self.server.hass.services.services.items()):
            write("<tr><td>{}</td><td>{}</td><td>".format(
                _get_domain_icon(domain), domain))

            write(", ".join(
                "<a href='#' data-service='{0}/{1}'>{1}</a>".format(
                    domain, service) for service in sorted(services)))

            write("</td></tr>")

        write(("</table></div></div>"

               "<div class='col-xs-6'>"
               "<div class='panel panel-primary'>"
               "<div class='panel-heading'><h2 class='panel-title'>"
               "     Call Service</h2></div>"
               "<div class='panel-body'>"
               "<form method='post' action='/call_service' "
               "     class='form-horizontal form-call-service'>"
               "<input type='hidden' name='api_password' value='{}'>"

               "<div class='form-group'>"
               "  <label for='domain' class='col-xs-3 control-label'>"
               "     Domain</label>"
               "  <div class='col-xs-9'>"
               "     <input type='text' class='form-control' id='domain'"
               "       name='domain' placeholder='Service Domain'>"
               "  </div>"
               "</div>"

               "<div class='form-group'>"
               "  <label for='service' class='col-xs-3 control-label'>"
               "     Service</label>"
               "  <div class='col-xs-9'>"
               "    <input type='text' class='form-control' id='service'"
               "      name='service' placeholder='Service name'>"
               "  </div>"
               "</div>"

               "<div class='form-group'>"
               "  <label for='service_data' class='col-xs-3 control-label'>"
               "    Service data</label>"
               "  <div class='col-xs-9'>"
               "    <textarea rows='3' class='form-control' id='service_data'"
               "      name='service_data' placeholder='Service Data "
               "(JSON, optional)'></textarea>"
               "  </div>"
               "</div>"

               "<div class='form-group'>"
               "  <div class='col-xs-offset-3 col-xs-9'>"
               "    <button type='submit' class='btn btn-default'>"
               "    Call Service</button>"
               "  </div>"
               "</div>"
               "</form>"
               "</div></div></div>"
               "</div>").format(self.server.api_password))

        # Describe bus/events:
        write(("<div class='row'>"
               "<div class='col-xs-6'>"
               "<div class='panel panel-primary'>"
               "<div class='panel-heading'><h2 class='panel-title'>"
               "     Events</h2></div>"
               "<table class='table'>"
               "<tr><th>Event</th><th>Listeners</th></tr>"))

        for event, listener_count in sorted(
                self.server.hass.bus.listeners.items()):
            write("<tr><td>{}</td><td>{}</td></tr>".format(
                event, listener_count))

        write(("</table></div></div>"

               "<div class='col-xs-6'>"
               "<div class='panel panel-primary'>"
               "<div class='panel-heading'><h2 class='panel-title'>"
               "     Fire Event</h2></div>"
               "<div class='panel-body'>"
               "<form method='post' action='/fire_event' "
               "     class='form-horizontal form-fire-event'>"
               "<input type='hidden' name='api_password' value='{}'>"

               "<div class='form-group'>"
               "  <label for='event_type' class='col-xs-3 control-label'>"
               "     Event type</label>"
               "  <div class='col-xs-9'>"
               "     <input type='text' class='form-control' id='event_type'"
               "      name='event_type' placeholder='Event Type'>"
               "  </div>"
               "</div>"

               "<div class='form-group'>"
               "  <label for='event_data' class='col-xs-3 control-label'>"
               "     Event data</label>"
               "  <div class='col-xs-9'>"
               "     <textarea rows='3' class='form-control' id='event_data'"
               "      name='event_data' placeholder='Event Data "
               "(JSON, optional)'></textarea>"
               "  </div>"
               "</div>"

               "<div class='form-group'>"
               "   <div class='col-xs-offset-3 col-xs-9'>"
               "     <button type='submit' class='btn btn-default'>"
               "     Fire Event</button>"
               "   </div>"
               "</div>"
               "</form>"
               "</div></div></div>"
               "</div>").format(self.server.api_password))

        write("</div></body></html>")

    # pylint: disable=invalid-name
    def _handle_change_state(self, path_match, data):
        """ Handles updating the state of an entity.

        This handles the following paths:
        /change_state
        /api/states/<entity_id>
        """
        try:
            try:
                entity_id = path_match.group('entity_id')
            except IndexError:
                # If group 'entity_id' does not exist in path_match
                entity_id = data['entity_id'][0]

            new_state = data['new_state'][0]

            try:
                attributes = json.loads(data['attributes'][0])
            except KeyError:
                # Happens if key 'attributes' does not exist
                attributes = None

            # Write state
            self.server.hass.states.set(entity_id, new_state, attributes)

            # Return state if json, else redirect to main page
            if self.use_json:
                state = self.server.hass.states.get(entity_id)

                self._write_json(state.as_dict(),
                                 status_code=HTTP_CREATED,
                                 location=
                                 rem.URL_API_STATES_ENTITY.format(entity_id))
            else:
                self._message(
                    "State of {} changed to {}".format(entity_id, new_state))

        except KeyError:
            # If new_state don't exist in post data
            self._message(
                "No new_state submitted.", HTTP_BAD_REQUEST)

        except ValueError:
            # Occurs during error parsing json
            self._message(
                "Invalid JSON for attributes", HTTP_UNPROCESSABLE_ENTITY)

    # pylint: disable=invalid-name
    def _handle_fire_event(self, path_match, data):
        """ Handles firing of an event.

        This handles the following paths:
        /fire_event
        /api/events/<event_type>

        Events from /api are threated as remote events.
        """
        try:
            try:
                event_type = path_match.group('event_type')
                event_origin = ha.EventOrigin.remote
            except IndexError:
                # If group event_type does not exist in path_match
                event_type = data['event_type'][0]
                event_origin = ha.EventOrigin.local

            if 'event_data' in data:
                event_data = json.loads(data['event_data'][0])
            else:
                event_data = None

            # Special case handling for event STATE_CHANGED
            # We will try to convert state dicts back to State objects
            if event_type == ha.EVENT_STATE_CHANGED and event_data:
                for key in ('old_state', 'new_state'):
                    state = ha.State.from_dict(event_data.get(key))

                    if state:
                        event_data[key] = state

            self.server.hass.bus.fire(event_type, event_data, event_origin)

            self._message("Event {} fired.".format(event_type))

        except KeyError:
            # Occurs if event_type does not exist in data
            self._message("No event_type received.", HTTP_BAD_REQUEST)

        except ValueError:
            # Occurs during error parsing json
            self._message(
                "Invalid JSON for event_data", HTTP_UNPROCESSABLE_ENTITY)

    def _handle_call_service(self, path_match, data):
        """ Handles calling a service.

        This handles the following paths:
        /call_service
        /api/services/<domain>/<service>
        """
        try:
            try:
                domain = path_match.group('domain')
                service = path_match.group('service')
            except IndexError:
                # If group domain or service does not exist in path_match
                domain = data['domain'][0]
                service = data['service'][0]

            try:
                service_data = json.loads(data['service_data'][0])
            except KeyError:
                # Happens if key 'service_data' does not exist
                service_data = None

            self.server.hass.call_service(domain, service, service_data)

            self._message("Service {}/{} called.".format(domain, service))

        except KeyError:
            # Occurs if domain or service does not exist in data
            self._message("No domain or service received.", HTTP_BAD_REQUEST)

        except ValueError:
            # Occurs during error parsing json
            self._message(
                "Invalid JSON for service_data", HTTP_UNPROCESSABLE_ENTITY)

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
            self._message("State does not exist.", HTTP_UNPROCESSABLE_ENTITY)

    def _handle_get_api_events(self, path_match, data):
        """ Handles getting overview of event listeners. """
        self._write_json({'event_listeners': self.server.hass.bus.listeners})

    def _handle_get_api_services(self, path_match, data):
        """ Handles getting overview of services. """
        self._write_json({'services': self.server.hass.services.services})

    def _handle_post_api_event_forward(self, path_match, data):
        """ Handles adding an event forwarding target. """

        try:
            host = data['host'][0]
            api_password = data['api_password'][0]

            port = int(data['port'][0]) if 'port' in data else None

            if self.server.event_forwarder is None:
                self.server.event_forwarder = \
                    rem.EventForwarder(self.server.hass)

            api = rem.API(host, api_password, port)

            self.server.event_forwarder.connect(api)

            self._message("Event forwarding setup.")

        except KeyError:
            # Occurs if domain or service does not exist in data
            self._message("No host or api_password received.",
                          HTTP_BAD_REQUEST)

        except ValueError:
            # Occurs during error parsing port
            self._message(
                "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)

    def _handle_delete_api_event_forward(self, path_match, data):
        """ Handles deleting an event forwarding target. """

        try:
            host = data['host'][0]

            port = int(data['port'][0]) if 'port' in data else None

            if self.server.event_forwarder is not None:
                api = rem.API(host, None, port)

                self.server.event_forwarder.disconnect(api)

            self._message("Event forwarding cancelled.")

        except KeyError:
            # Occurs if domain or service does not exist in data
            self._message("No host or api_password received.",
                          HTTP_BAD_REQUEST)

        except ValueError:
            # Occurs during error parsing port
            self._message(
                "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)

    def _handle_get_static(self, path_match, data):
        """ Returns a static file. """
        req_file = util.sanitize_filename(path_match.group('file'))

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

        if data:
            self.wfile.write(
                json.dumps(data, indent=4, sort_keys=True,
                           cls=rem.JSONEncoder).encode("UTF-8"))
