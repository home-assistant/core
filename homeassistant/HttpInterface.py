"""
homeassistant.httpinterface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides an HTTP interface for debug purposes.

"""

import threading
import urlparse
import logging
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

import requests

from .core import EVENT_START, EVENT_SHUTDOWN

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8080

class HTTPInterface(threading.Thread):
    """ Provides an HTTP interface for Home Assistant. """

    def __init__(self, eventbus, statemachine):
        threading.Thread.__init__(self)

        self.server = HTTPServer((SERVER_HOST, SERVER_PORT), RequestHandler)

        self.server.eventbus = eventbus
        self.server.statemachine = statemachine

        self._stop = threading.Event()

        eventbus.listen(EVENT_START, lambda event: self.start())
        eventbus.listen(EVENT_SHUTDOWN, lambda event: self.stop())

    def run(self):
        """ Start the HTTP interface. """
        logging.getLogger(__name__).info("Starting")

        while not self._stop.is_set():
            self.server.handle_request()


    def stop(self):
        """ Stop the HTTP interface. """
        self._stop.set()

        # Trigger a fake request to get the server to quit
        requests.get("http://{}:{}".format(SERVER_HOST, SERVER_PORT))

class RequestHandler(BaseHTTPRequestHandler):
    """ Handles incoming HTTP requests """

    #Handler for the GET requests
    def do_GET(self):
        """ Handle incoming GET requests. """

        if self.path == "/":
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()

            write = self.wfile.write

            # Describe state machine:
            categories = []

            write("<table>")
            write("<tr><th>Name</th><th>State</th><th>Last Changed</th></tr>")

            for category, state, last_changed in self.server.statemachine.get_states():
                categories.append(category)

                write("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(category, state, last_changed.strftime("%H:%M:%S %d-%m-%Y")))

            write("</table>")

            # Small form to change the state
            write("<br />Change state:<br />")
            write("<form action='change_state' method='POST'>")
            write("<select name='category'>")

            for category in categories:
                write("<option>{}</option>".format(category))

            write("</select>")

            write("<input name='new_state' />")
            write("<input type='submit' value='set state' />")
            write("</form>")

            # Describe event bus:
            for category in self.server.eventbus.listeners:
                write("Event {}: {} listeners<br />".format(category, len(self.server.eventbus.listeners[category])))

        else:
            self.send_response(404)


    def do_POST(self):
        """ Handle incoming POST requests. """

        length = int(self.headers['Content-Length'])
        post_data = urlparse.parse_qs(self.rfile.read(length))

        if self.path == "/change_state":
            self.server.statemachine.set_state(post_data['category'][0], post_data['new_state'][0])

            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()

        else:
            self.send_response(404)
