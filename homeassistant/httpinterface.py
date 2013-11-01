"""
homeassistant.httpinterface
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

/api/states - GET
Returns a list of categories for which a state is available
Example result:
{
    "categories": [
        "Paulus_Nexus_4",
        "weather.sun",
        "all_devices"
    ]
}

/api/states/<category> - GET
Returns the current state from a category
Example result:
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013",
        "next_setting": "18:00:31 29-10-2013"
    },
    "category": "weather.sun",
    "last_changed": "23:24:33 28-10-2013",
    "state": "below_horizon"
}

/api/states/<category> - POST
Updates the current state of a category. Returns status code 201 if successful
with location header of updated resource and as body the new state.
parameter: new_state - string
optional parameter: attributes - JSON encoded object
Example result:
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013",
        "next_setting": "18:00:31 29-10-2013"
    },
    "category": "weather.sun",
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
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from urlparse import urlparse, parse_qs

import homeassistant as ha

SERVER_PORT = 8123

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422

URL_ROOT = "/"

URL_STATES_CATEGORY = "/states/{}"
URL_API_STATES = "/api/states"
URL_API_STATES_CATEGORY = "/api/states/{}"

URL_EVENTS_EVENT = "/events/{}"
URL_API_EVENTS = "/api/events"
URL_API_EVENTS_EVENT = "/api/events/{}"


class HTTPInterface(threading.Thread):
    """ Provides an HTTP interface for Home Assistant. """

    # pylint: disable=too-many-arguments
    def __init__(self, eventbus, statemachine, api_password,
                 server_port=None, server_host=None):
        threading.Thread.__init__(self)

        self.daemon = True

        if not server_port:
            server_port = SERVER_PORT

        # If no server host is given, accept all incoming requests
        if not server_host:
            server_host = '0.0.0.0'

        self.server = HTTPServer((server_host, server_port), RequestHandler)

        self.server.flash_message = None
        self.server.logger = logging.getLogger(__name__)
        self.server.eventbus = eventbus
        self.server.statemachine = statemachine
        self.server.api_password = api_password

        eventbus.listen_once(ha.EVENT_START, lambda event: self.start())

    def run(self):
        """ Start the HTTP interface. """
        self.server.logger.info("Starting")

        self.server.serve_forever()

class RequestHandler(BaseHTTPRequestHandler):
    """ Handles incoming HTTP requests """

    PATHS = [ ('GET', '/', '_handle_get_root'),

              # /states
              ('GET', '/states', '_handle_get_states'),
              ('GET', re.compile(r'/states/(?P<category>[a-zA-Z\.\_0-9]+)'),
                                    '_handle_get_states_category'),
              ('POST', re.compile(r'/states/(?P<category>[a-zA-Z\.\_0-9]+)'),
                                    '_handle_post_states_category'),

              # /events
              ('POST', re.compile(r'/events/(?P<event_type>\w+)'),
                                    '_handle_post_events_event_type')
                ]

    def _handle_request(self, method): # pylint: disable=too-many-branches
        """ Does some common checks and calls appropriate method. """
        url = urlparse(self.path)

        # Read query input
        data = parse_qs(url.query)

        # Did we get post input ?
        content_length = int(self.headers.get('Content-Length', 0))

        if content_length:
            data.update(parse_qs(self.rfile.read(content_length)))

        try:
            api_password = data['api_password'][0]
        except KeyError:
            api_password = ''

        # We respond to API requests with JSON
        # For other requests we respond with html
        if url.path.startswith('/api/'):
            path = url.path[4:]
            # pylint: disable=attribute-defined-outside-init
            self.use_json = True

        else:
            path = url.path
            # pylint: disable=attribute-defined-outside-init
            self.use_json = False


        path_matched_but_not_method = False
        handle_request_method = False

        # Check every url to find matching result
        for t_method, t_path, t_handler in RequestHandler.PATHS:

            # we either do string-comparison or regular expression matching
            if isinstance(t_path, str):
                path_match = path == t_path
            else:
                path_match = t_path.match(path) #pylint:disable=maybe-no-member


            if path_match and method == t_method:
                # Call the method
                handle_request_method = getattr(self, t_handler)
                break

            elif path_match:
                path_matched_but_not_method = True


        if handle_request_method:

            if self._verify_api_password(api_password):
                handle_request_method(path_match, data)

        elif path_matched_but_not_method:
            self.send_response(HTTP_METHOD_NOT_ALLOWED)

        else:
            self.send_response(HTTP_NOT_FOUND)


    def do_GET(self): # pylint: disable=invalid-name
        """ GET request handler. """
        self._handle_request('GET')

    def do_POST(self): # pylint: disable=invalid-name
        """ POST request handler. """
        self._handle_request('POST')

    def _verify_api_password(self, api_password):
        """ Helper method to verify the API password
            and take action if incorrect. """
        if api_password == self.server.api_password:
            return True

        elif self.use_json:
            self._message("API password missing or incorrect.",
                                                            HTTP_UNAUTHORIZED)

        else:
            self.send_response(HTTP_OK)
            self.send_header('Content-type','text/html')
            self.end_headers()

            self.wfile.write((
                   "<html>"
                   "<head><title>Home Assistant</title></head>"
                   "<body>"
                   "<form action='/' method='GET'>"
                   "API password: <input name='api_password' />"
                   "<input type='submit' value='submit' />"
                   "</form>"
                   "</body></html>"))

        return False

    # pylint: disable=unused-argument
    def _handle_get_root(self, path_match, data):
        """ Renders the debug interface. """

        write = lambda txt: self.wfile.write(txt+"\n")

        self.send_response(HTTP_OK)
        self.send_header('Content-type','text/html')
        self.end_headers()

        write(("<html>"
               "<head><title>Home Assistant</title></head>"
               "<body>"))

        # Flash message support
        if self.server.flash_message:
            write("<h3>{}</h3>".format(self.server.flash_message))

            self.server.flash_message = None

        # Describe state machine:
        categories = []

        write(("<table><tr>"
               "<th>Name</th><th>State</th>"
               "<th>Last Changed</th><th>Attributes</th></tr>"))

        for category in \
            sorted(self.server.statemachine.categories,
                                    key=lambda key: key.lower()):

            categories.append(category)

            state = self.server.statemachine.get_state(category)

            attributes = "<br>".join(
                ["{}: {}".format(attr, state['attributes'][attr])
                 for attr in state['attributes']])

            write(("<tr>"
                   "<td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
                   "</tr>").
                format(category,
                       state['state'],
                       state['last_changed'],
                       attributes))

        write("</table>")

        # Describe event bus:
        write(("<table><tr><th>Event</th><th>Listeners</th></tr>"))

        for category in sorted(self.server.eventbus.listeners,
                                        key=lambda key: key.lower()):
            write("<tr><td>{}</td><td>{}</td></tr>".
                format(category,
                       len(self.server.eventbus.listeners[category])))

        # Form to allow firing events
        write("</table>")

        write("</body></html>")

    # pylint: disable=unused-argument
    def _handle_get_states(self, path_match, data):
        """ Returns the categories which state is being tracked. """
        self._write_json({'categories': self.server.statemachine.categories})

    # pylint: disable=unused-argument
    def _handle_get_states_category(self, path_match, data):
        """ Returns the state of a specific category. """
        category = path_match.group('category')

        state = self.server.statemachine.get_state(category)

        if state:
            state['category'] = category

            self._write_json(state)

        else:
            # If category does not exist
            self._message("State does not exist.", HTTP_UNPROCESSABLE_ENTITY)

    def _handle_post_states_category(self, path_match, data):
        """ Handles updating the state of a category. """
        try:
            category = path_match.group('category')

            new_state = data['new_state'][0]

            try:
                attributes = json.loads(data['attributes'][0])
            except KeyError:
                # Happens if key 'attributes' does not exist
                attributes = None

            # Write state
            self.server.statemachine.set_state(category,
                                               new_state,
                                               attributes)

            # Return state
            state = self.server.statemachine.get_state(category)

            state['category'] = category

            self._write_json(state, status_code=HTTP_CREATED,
                             location=URL_STATES_CATEGORY.format(category))

        except KeyError:
            # If new_state don't exist in post data
            self._message("No new_state submitted.",
                                                HTTP_BAD_REQUEST)

        except ValueError:
            # Occurs during error parsing json
            self._message("Invalid JSON for attributes",
                                                HTTP_UNPROCESSABLE_ENTITY)

    def _handle_post_events_event_type(self, path_match, data):
        """ Handles firing of an event. """
        event_type = path_match.group('event_type')

        try:
            try:
                event_data = json.loads(data['event_data'][0])
            except KeyError:
                # Happens if key 'event_data' does not exist
                event_data = None

            self.server.eventbus.fire(event_type, event_data)

            self._message("Event {} fired.".format(event_type))

        except ValueError:
            # Occurs during error parsing json
            self._message("Invalid JSON for event_data",
                                                    HTTP_UNPROCESSABLE_ENTITY)

    def _message(self, message, status_code=HTTP_OK):
        """ Helper method to return a message to the caller. """
        if self.use_json:
            self._write_json({'message': message}, status_code=status_code)
        else:
            self.server.flash_message = message
            self._redirect('/')

    def _redirect(self, location):
        """ Helper method to redirect caller. """
        self.send_response(HTTP_MOVED_PERMANENTLY)
        self.send_header("Location", "{}?api_password={}".
                            format(location, self.server.api_password))
        self.end_headers()

    def _write_json(self, data=None, status_code=HTTP_OK, location=None):
        """ Helper method to return JSON to the caller. """
        self.send_response(status_code)
        self.send_header('Content-type','application/json')

        if location:
            self.send_header('Location', location)

        self.end_headers()

        if data:
            self.wfile.write(json.dumps(data, indent=4, sort_keys=True))
