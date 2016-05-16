"""
This module provides an API and a HTTP interface for debug purposes.

For more details about the RESTful API, please refer to the documentation at
https://home-assistant.io/developers/api/
"""
import gzip
import hmac
import json
import logging
import ssl
import threading
import time
from datetime import timedelta
from http import cookies
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse
import voluptuous as vol

import homeassistant.bootstrap as bootstrap
import homeassistant.core as ha
import homeassistant.remote as rem
import homeassistant.util as util
import homeassistant.util.dt as date_util
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONTENT_TYPE_JSON, CONTENT_TYPE_TEXT_PLAIN, HTTP_HEADER_ACCEPT_ENCODING,
    HTTP_HEADER_CACHE_CONTROL, HTTP_HEADER_CONTENT_ENCODING,
    HTTP_HEADER_CONTENT_LENGTH, HTTP_HEADER_CONTENT_TYPE, HTTP_HEADER_EXPIRES,
    HTTP_HEADER_HA_AUTH, HTTP_HEADER_VARY,
    HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN,
    HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS, HTTP_METHOD_NOT_ALLOWED,
    HTTP_NOT_FOUND, HTTP_OK, HTTP_UNAUTHORIZED, HTTP_UNPROCESSABLE_ENTITY,
    ALLOWED_CORS_HEADERS,
    SERVER_PORT, URL_ROOT, URL_API_EVENT_FORWARD)

DOMAIN = "http"

CONF_API_PASSWORD = "api_password"
CONF_SERVER_HOST = "server_host"
CONF_SERVER_PORT = "server_port"
CONF_DEVELOPMENT = "development"
CONF_SSL_CERTIFICATE = 'ssl_certificate'
CONF_SSL_KEY = 'ssl_key'
CONF_CORS_ORIGINS = 'cors_allowed_origins'

DATA_API_PASSWORD = 'api_password'

# Throttling time in seconds for expired sessions check
SESSION_CLEAR_INTERVAL = timedelta(seconds=20)
SESSION_TIMEOUT_SECONDS = 1800
SESSION_KEY = 'sessionId'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_PASSWORD): cv.string,
        vol.Optional(CONF_SERVER_HOST): cv.string,
        vol.Optional(CONF_SERVER_PORT, default=SERVER_PORT):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Optional(CONF_DEVELOPMENT): cv.string,
        vol.Optional(CONF_SSL_CERTIFICATE): cv.isfile,
        vol.Optional(CONF_SSL_KEY): cv.isfile,
        vol.Optional(CONF_CORS_ORIGINS): cv.ensure_list
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the HTTP API and debug interface."""
    conf = config.get(DOMAIN, {})

    api_password = util.convert(conf.get(CONF_API_PASSWORD), str)

    # If no server host is given, accept all incoming requests
    server_host = conf.get(CONF_SERVER_HOST, '0.0.0.0')
    server_port = conf.get(CONF_SERVER_PORT, SERVER_PORT)
    development = str(conf.get(CONF_DEVELOPMENT, "")) == "1"
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)
    ssl_key = conf.get(CONF_SSL_KEY)
    cors_origins = conf.get(CONF_CORS_ORIGINS, [])

    try:
        server = HomeAssistantHTTPServer(
            (server_host, server_port), RequestHandler, hass, api_password,
            development, ssl_certificate, ssl_key, cors_origins)
    except OSError:
        # If address already in use
        _LOGGER.exception("Error setting up HTTP server")
        return False

    hass.bus.listen_once(
        ha.EVENT_HOMEASSISTANT_START,
        lambda event:
        threading.Thread(target=server.start, daemon=True,
                         name='HTTP-server').start())

    hass.http = server
    hass.config.api = rem.API(server_host if server_host != '0.0.0.0'
                              else util.get_local_ip(),
                              api_password, server_port,
                              ssl_certificate is not None)

    return True


# pylint: disable=too-many-instance-attributes
class HomeAssistantHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle HTTP requests in a threaded fashion."""

    # pylint: disable=too-few-public-methods
    allow_reuse_address = True
    daemon_threads = True

    # pylint: disable=too-many-arguments
    def __init__(self, server_address, request_handler_class,
                 hass, api_password, development, ssl_certificate, ssl_key,
                 cors_origins):
        """Initialize the server."""
        super().__init__(server_address, request_handler_class)

        self.server_address = server_address
        self.hass = hass
        self.api_password = api_password
        self.development = development
        self.paths = []
        self.sessions = SessionStore()
        self.use_ssl = ssl_certificate is not None
        self.cors_origins = cors_origins

        # We will lazy init this one if needed
        self.event_forwarder = None

        if development:
            _LOGGER.info("running http in development mode")

        if ssl_certificate is not None:
            context = ssl.create_default_context(
                purpose=ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(ssl_certificate, keyfile=ssl_key)
            self.socket = context.wrap_socket(self.socket, server_side=True)

    def start(self):
        """Start the HTTP server."""
        def stop_http(event):
            """Stop the HTTP server."""
            self.shutdown()

        self.hass.bus.listen_once(ha.EVENT_HOMEASSISTANT_STOP, stop_http)

        protocol = 'https' if self.use_ssl else 'http'

        _LOGGER.info(
            "Starting web interface at %s://%s:%d",
            protocol, self.server_address[0], self.server_address[1])

        # 31-1-2015: Refactored frontend/api components out of this component
        # To prevent stuff from breaking, load the two extracted components
        bootstrap.setup_component(self.hass, 'api')
        bootstrap.setup_component(self.hass, 'frontend')

        self.serve_forever()

    def register_path(self, method, url, callback, require_auth=True):
        """Register a path with the server."""
        self.paths.append((method, url, callback, require_auth))

    def log_message(self, fmt, *args):
        """Redirect built-in log to HA logging."""
        # pylint: disable=no-self-use
        _LOGGER.info(fmt, *args)


# pylint: disable=too-many-public-methods,too-many-locals
class RequestHandler(SimpleHTTPRequestHandler):
    """Handle incoming HTTP requests.

    We extend from SimpleHTTPRequestHandler instead of Base so we
    can use the guess content type methods.
    """

    server_version = "HomeAssistant/1.0"

    def __init__(self, req, client_addr, server):
        """Constructor, call the base constructor and set up session."""
        # Track if this was an authenticated request
        self.authenticated = False
        SimpleHTTPRequestHandler.__init__(self, req, client_addr, server)
        self.protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *arguments):
        """Redirect built-in log to HA logging."""
        if self.server.api_password is None:
            _LOGGER.info(fmt, *arguments)
        else:
            _LOGGER.info(
                fmt, *(arg.replace(self.server.api_password, '*******')
                       if isinstance(arg, str) else arg for arg in arguments))

    def _handle_request(self, method):  # pylint: disable=too-many-branches
        """Perform some common checks and call appropriate method."""
        url = urlparse(self.path)

        # Read query input. parse_qs gives a list for each value, we want last
        data = {key: data[-1] for key, data in parse_qs(url.query).items()}

        # Did we get post input ?
        content_length = int(self.headers.get(HTTP_HEADER_CONTENT_LENGTH, 0))

        if content_length:
            body_content = self.rfile.read(content_length).decode("UTF-8")

            try:
                data.update(json.loads(body_content))
            except (TypeError, ValueError):
                # TypeError if JSON object is not a dict
                # ValueError if we could not parse JSON
                _LOGGER.exception(
                    "Exception parsing JSON: %s", body_content)
                self.write_json_message(
                    "Error parsing JSON", HTTP_UNPROCESSABLE_ENTITY)
                return

        if self.verify_session():
            # The user has a valid session already
            self.authenticated = True
        elif self.server.api_password is None:
            # No password is set, so everyone is authenticated
            self.authenticated = True
        elif hmac.compare_digest(self.headers.get(HTTP_HEADER_HA_AUTH, ''),
                                 self.server.api_password):
            # A valid auth header has been set
            self.authenticated = True
        elif hmac.compare_digest(data.get(DATA_API_PASSWORD, ''),
                                 self.server.api_password):
            # A valid password has been specified
            self.authenticated = True
        else:
            self.authenticated = False

        # we really shouldn't need to forward the password from here
        if url.path not in [URL_ROOT, URL_API_EVENT_FORWARD]:
            data.pop(DATA_API_PASSWORD, None)

        if '_METHOD' in data:
            method = data.pop('_METHOD')

        # Var to keep track if we found a path that matched a handler but
        # the method was different
        path_matched_but_not_method = False

        # Var to hold the handler for this path and method if found
        handle_request_method = False
        require_auth = True

        # Check every handler to find matching result
        for t_method, t_path, t_handler, t_auth in self.server.paths:
            # we either do string-comparison or regular expression matching
            # pylint: disable=maybe-no-member
            if isinstance(t_path, str):
                path_match = url.path == t_path
            else:
                path_match = t_path.match(url.path)

            if path_match and method == t_method:
                # Call the method
                handle_request_method = t_handler
                require_auth = t_auth
                break

            elif path_match:
                path_matched_but_not_method = True

        # Did we find a handler for the incoming request?
        if handle_request_method:
            # For some calls we need a valid password
            msg = "API password missing or incorrect."
            if require_auth and not self.authenticated:
                self.write_json_message(msg, HTTP_UNAUTHORIZED)
                _LOGGER.warning('%s Source IP: %s',
                                msg,
                                self.client_address[0])
                return

            handle_request_method(self, path_match, data)

        elif path_matched_but_not_method:
            self.send_response(HTTP_METHOD_NOT_ALLOWED)
            self.end_headers()

        else:
            self.send_response(HTTP_NOT_FOUND)
            self.end_headers()

    def do_HEAD(self):  # pylint: disable=invalid-name
        """HEAD request handler."""
        self._handle_request('HEAD')

    def do_GET(self):  # pylint: disable=invalid-name
        """GET request handler."""
        self._handle_request('GET')

    def do_POST(self):  # pylint: disable=invalid-name
        """POST request handler."""
        self._handle_request('POST')

    def do_PUT(self):  # pylint: disable=invalid-name
        """PUT request handler."""
        self._handle_request('PUT')

    def do_DELETE(self):  # pylint: disable=invalid-name
        """DELETE request handler."""
        self._handle_request('DELETE')

    def write_json_message(self, message, status_code=HTTP_OK):
        """Helper method to return a message to the caller."""
        self.write_json({'message': message}, status_code=status_code)

    def write_json(self, data=None, status_code=HTTP_OK, location=None):
        """Helper method to return JSON to the caller."""
        json_data = json.dumps(data, indent=4, sort_keys=True,
                               cls=rem.JSONEncoder).encode('UTF-8')
        self.send_response(status_code)

        if location:
            self.send_header('Location', location)

        self.set_session_cookie_header()

        self.write_content(json_data, CONTENT_TYPE_JSON)

    def write_text(self, message, status_code=HTTP_OK):
        """Helper method to return a text message to the caller."""
        msg_data = message.encode('UTF-8')
        self.send_response(status_code)
        self.set_session_cookie_header()

        self.write_content(msg_data, CONTENT_TYPE_TEXT_PLAIN)

    def write_file(self, path, cache_headers=True):
        """Return a file to the user."""
        try:
            with open(path, 'rb') as inp:
                self.write_file_pointer(self.guess_type(path), inp,
                                        cache_headers)

        except IOError:
            self.send_response(HTTP_NOT_FOUND)
            self.end_headers()
            _LOGGER.exception("Unable to serve %s", path)

    def write_file_pointer(self, content_type, inp, cache_headers=True):
        """Helper function to write a file pointer to the user."""
        self.send_response(HTTP_OK)

        if cache_headers:
            self.set_cache_header()
        self.set_session_cookie_header()

        self.write_content(inp.read(), content_type)

    def write_content(self, content, content_type=None):
        """Helper method to write content bytes to output stream."""
        if content_type is not None:
            self.send_header(HTTP_HEADER_CONTENT_TYPE, content_type)

        if 'gzip' in self.headers.get(HTTP_HEADER_ACCEPT_ENCODING, ''):
            content = gzip.compress(content)

            self.send_header(HTTP_HEADER_CONTENT_ENCODING, "gzip")
            self.send_header(HTTP_HEADER_VARY, HTTP_HEADER_ACCEPT_ENCODING)

        self.send_header(HTTP_HEADER_CONTENT_LENGTH, str(len(content)))

        cors_check = (self.headers.get("Origin") in self.server.cors_origins)

        cors_headers = ", ".join(ALLOWED_CORS_HEADERS)

        if self.server.cors_origins and cors_check:
            self.send_header(HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN,
                             self.headers.get("Origin"))
            self.send_header(HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS,
                             cors_headers)
        self.end_headers()

        if self.command == 'HEAD':
            return

        self.wfile.write(content)

    def set_cache_header(self):
        """Add cache headers if not in development."""
        if self.server.development:
            return

        # 1 year in seconds
        cache_time = 365 * 86400

        self.send_header(
            HTTP_HEADER_CACHE_CONTROL,
            "public, max-age={}".format(cache_time))
        self.send_header(
            HTTP_HEADER_EXPIRES,
            self.date_time_string(time.time()+cache_time))

    def set_session_cookie_header(self):
        """Add the header for the session cookie and return session ID."""
        if not self.authenticated:
            return None

        session_id = self.get_cookie_session_id()

        if session_id is not None:
            self.server.sessions.extend_validation(session_id)
            return session_id

        self.send_header(
            'Set-Cookie',
            '{}={}'.format(SESSION_KEY, self.server.sessions.create())
        )

        return session_id

    def verify_session(self):
        """Verify that we are in a valid session."""
        return self.get_cookie_session_id() is not None

    def get_cookie_session_id(self):
        """Extract the current session ID from the cookie.

        Return None if not set or invalid.
        """
        if 'Cookie' not in self.headers:
            return None

        cookie = cookies.SimpleCookie()
        try:
            cookie.load(self.headers["Cookie"])
        except cookies.CookieError:
            return None

        morsel = cookie.get(SESSION_KEY)

        if morsel is None:
            return None

        session_id = cookie[SESSION_KEY].value

        if self.server.sessions.is_valid(session_id):
            return session_id

        return None

    def destroy_session(self):
        """Destroy the session."""
        session_id = self.get_cookie_session_id()

        if session_id is None:
            return

        self.send_header('Set-Cookie', '')
        self.server.sessions.destroy(session_id)


def session_valid_time():
    """Time till when a session will be valid."""
    return date_util.utcnow() + timedelta(seconds=SESSION_TIMEOUT_SECONDS)


class SessionStore(object):
    """Responsible for storing and retrieving HTTP sessions."""

    def __init__(self):
        """Setup the session store."""
        self._sessions = {}
        self._lock = threading.RLock()

    @util.Throttle(SESSION_CLEAR_INTERVAL)
    def _remove_expired(self):
        """Remove any expired sessions."""
        now = date_util.utcnow()
        for key in [key for key, valid_time in self._sessions.items()
                    if valid_time < now]:
            self._sessions.pop(key)

    def is_valid(self, key):
        """Return True if a valid session is given."""
        with self._lock:
            self._remove_expired()

            return (key in self._sessions and
                    self._sessions[key] > date_util.utcnow())

    def extend_validation(self, key):
        """Extend a session validation time."""
        with self._lock:
            if key not in self._sessions:
                return
            self._sessions[key] = session_valid_time()

    def destroy(self, key):
        """Destroy a session by key."""
        with self._lock:
            self._sessions.pop(key, None)

    def create(self):
        """Create a new session."""
        with self._lock:
            session_id = util.get_random_string(20)

            while session_id in self._sessions:
                session_id = util.get_random_string(20)

            self._sessions[session_id] = session_valid_time()

            return session_id
