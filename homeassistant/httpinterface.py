"""
homeassistant.httpinterface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides an API and a HTTP interface for debug purposes.

By default it will run on port 8080.

All API calls have to be accompanied by an 'api_password' parameter.

The api supports the following actions:

/api/state/change - POST
parameter: category - string
parameter: new_state - string
Changes category 'category' to 'new_state'
It is possible to sent multiple values for category and new_state.
If the number of values for category and new_state do not match only
combinations where both values are supplied will be set.

/api/event/fire - POST
parameter: event_name - string
parameter: event_data - JSON-string (optional)
Fires an 'event_name' event containing data from 'event_data'

"""

import json
import threading
import logging
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from urlparse import urlparse, parse_qs

import homeassistant
import homeassistant.util as util

SERVER_PORT = 8123

MESSAGE_STATUS_OK = "OK"
MESSAGE_STATUS_ERROR = "ERROR"
MESSAGE_STATUS_UNAUTHORIZED = "UNAUTHORIZED"

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

        eventbus.listen(homeassistant.EVENT_START, lambda event: self.start())

    def run(self):
        """ Start the HTTP interface. """
        self.server.logger.info("Starting")

        self.server.serve_forever()

class RequestHandler(BaseHTTPRequestHandler):
    """ Handles incoming HTTP requests """

    #Handler for the GET requests
    def do_GET(self):    # pylint: disable=invalid-name
        """ Handle incoming GET requests. """
        write = lambda txt: self.wfile.write(txt+"\n")

        url = urlparse(self.path)

        get_data = parse_qs(url.query)

        api_password = get_data.get('api_password', [''])[0]

        if url.path == "/":
            if self._verify_api_password(api_password, False):
                self.send_response(200)
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
                       "<th>Last Changed</th></tr>"))

                for category, state, last_changed in \
                        self.server.statemachine.get_states():

                    categories.append(category)

                    write("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".
                        format(category, state,
                               util.datetime_to_str(last_changed)))

                write("</table>")

                # Small form to change the state
                write(("<br />Change state:<br />"
                       "<form action='state/change' method='POST'>"))

                write("<input type='hidden' name='api_password' value='{}' />".
                        format(self.server.api_password))

                write("<select name='category'>")

                for category in categories:
                    write("<option>{}</option>".format(category))

                write("</select>")

                write(("<input name='new_state' />"
                       "<input type='submit' value='set state' />"
                       "</form>"))

                # Describe event bus:
                for category in self.server.eventbus.listeners:
                    write("Event {}: {} listeners<br />".format(category,
                            len(self.server.eventbus.listeners[category])))

                # Form to allow firing events
                write(("<br />"
                       "<form action='event/fire' method='POST'>"))

                write("<input type='hidden' name='api_password' value='{}' />".
                        format(self.server.api_password))

                write(("Event name: <input name='event_name' /><br />"
                       "Event data (json): <input name='event_data' /><br />"
                       "<input type='submit' value='fire event' />"
                       "</form>"))

                write("</body></html>")


        else:
            self.send_response(404)

    def do_POST(self):    # pylint: disable=invalid-name, too-many-branches
        """ Handle incoming POST requests. """

        length = int(self.headers['Content-Length'])
        post_data = parse_qs(self.rfile.read(length))

        if self.path.startswith('/api/'):
            action = self.path[5:]
            use_json = True

        else:
            action = self.path[1:]
            use_json = False

        given_api_password = post_data.get("api_password", [''])[0]

        # Action to change the state
        if action == "state/change":
            if self._verify_api_password(given_api_password, use_json):
                try:
                    changed = []

                    for category, new_state in zip(post_data['category'],
                                                   post_data['new_state']):

                        self.server.statemachine.set_state(category, new_state)

                        changed.append("{}={}".format(category, new_state))

                    self._message(use_json, "States changed: {}".
                                                format( ", ".join(changed) ) )

                except KeyError:
                    # If category or new_state don't exist in post data
                    self._message(use_json, "Invalid state received.",
                                                        MESSAGE_STATUS_ERROR)

        # Action to fire an event
        elif action == "event/fire":
            if self._verify_api_password(given_api_password, use_json):
                try:
                    event_name = post_data['event_name'][0]

                    if (not 'event_data' in post_data or
                        post_data['event_data'][0] == ""):

                        event_data = None

                    else:
                        event_data = json.loads(post_data['event_data'][0])

                    self.server.eventbus.fire(event_name, event_data)

                    self._message(use_json, "Event {} fired.".
                                                format(event_name))

                except ValueError:
                    # If JSON decode error
                    self._message(use_json, "Invalid event received (1).",
                                                        MESSAGE_STATUS_ERROR)

                except KeyError:
                    # If "event_name" not in post_data
                    self._message(use_json, "Invalid event received (2).",
                                                        MESSAGE_STATUS_ERROR)

        else:
            self.send_response(404)


    def _verify_api_password(self, api_password, use_json):
        """ Helper method to verify the API password
            and take action if incorrect. """
        if api_password == self.server.api_password:
            return True

        elif use_json:
            self._message(True, "API password missing or incorrect.",
                                                MESSAGE_STATUS_UNAUTHORIZED)

        else:
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()

            write = lambda txt: self.wfile.write(txt+"\n")

            write(("<html>"
                   "<head><title>Home Assistant</title></head>"
                   "<body>"
                   "<form action='/' method='GET'>"
                   "API password: <input name='api_password' />"
                   "<input type='submit' value='submit' />"
                   "</form>"
                   "</body></html>"))

        return False

    def _message(self, use_json, message, status=MESSAGE_STATUS_OK):
        """ Helper method to show a message to the user. """
        log_message = "{}: {}".format(status, message)

        if status == MESSAGE_STATUS_OK:
            self.server.logger.info(log_message)
            response_code = 200

        else:
            self.server.logger.error(log_message)
            response_code = (401 if status == MESSAGE_STATUS_UNAUTHORIZED
                                                                    else 400)

        if use_json:
            self.send_response(response_code)
            self.send_header('Content-type','application/json')
            self.end_headers()

            self.wfile.write(json.dumps({'status': status, 'message':message}))

        else:
            self.server.flash_message = message

            self.send_response(301)
            self.send_header("Location", "/?api_password={}".
                                format(self.server.api_password))
            self.end_headers()
