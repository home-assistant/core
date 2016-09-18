"""
This module provides WSGI application to serve the Home Assistant API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/http/
"""
import hmac
import json
import logging
import mimetypes
import threading
import re
import ssl
import voluptuous as vol

import homeassistant.remote as rem
from homeassistant import util
from homeassistant.const import (
    SERVER_PORT, HTTP_HEADER_HA_AUTH, HTTP_HEADER_CACHE_CONTROL,
    HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN,
    HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS, ALLOWED_CORS_HEADERS,
    EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START)
from homeassistant.core import split_entity_id
import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv

DOMAIN = 'http'
REQUIREMENTS = ('cherrypy==8.1.0', 'static3==0.7.0', 'Werkzeug==0.11.11')

CONF_API_PASSWORD = 'api_password'
CONF_APPROVED_IPS = 'approved_ips'
CONF_SERVER_HOST = 'server_host'
CONF_SERVER_PORT = 'server_port'
CONF_DEVELOPMENT = 'development'
CONF_SSL_CERTIFICATE = 'ssl_certificate'
CONF_SSL_KEY = 'ssl_key'
CONF_CORS_ORIGINS = 'cors_allowed_origins'

DATA_API_PASSWORD = 'api_password'

# TLS configuation follows the best-practice guidelines specified here:
# https://wiki.mozilla.org/Security/Server_Side_TLS
# Intermediate guidelines are followed.
SSL_VERSION = ssl.PROTOCOL_SSLv23
SSL_OPTS = ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
if hasattr(ssl, 'OP_NO_COMPRESSION'):
    SSL_OPTS |= ssl.OP_NO_COMPRESSION
CIPHERS = "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:" \
          "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:" \
          "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:" \
          "DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:" \
          "ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256:" \
          "ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:" \
          "ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:" \
          "ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA:" \
          "DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:" \
          "DHE-RSA-AES256-SHA:ECDHE-ECDSA-DES-CBC3-SHA:" \
          "ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA256:" \
          "AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:" \
          "AES256-SHA:DES-CBC3-SHA:!DSS"

_FINGERPRINT = re.compile(r'^(.+)-[a-z0-9]{32}\.(\w+)$', re.IGNORECASE)

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
        vol.Optional(CONF_CORS_ORIGINS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_APPROVED_IPS): vol.All(cv.ensure_list, [cv.string])
    }),
}, extra=vol.ALLOW_EXTRA)


class HideSensitiveFilter(logging.Filter):
    """Filter API password calls."""

    # pylint: disable=too-few-public-methods
    def __init__(self, hass):
        """Initialize sensitive data filter."""
        super().__init__()
        self.hass = hass

    def filter(self, record):
        """Hide sensitive data in messages."""
        if self.hass.wsgi.api_password is None:
            return True

        record.msg = record.msg.replace(self.hass.wsgi.api_password, '*******')

        return True


def setup(hass, config):
    """Set up the HTTP API and debug interface."""
    _LOGGER.addFilter(HideSensitiveFilter(hass))

    conf = config.get(DOMAIN, {})

    api_password = util.convert(conf.get(CONF_API_PASSWORD), str)
    server_host = conf.get(CONF_SERVER_HOST, '0.0.0.0')
    server_port = conf.get(CONF_SERVER_PORT, SERVER_PORT)
    development = str(conf.get(CONF_DEVELOPMENT, "")) == "1"
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)
    ssl_key = conf.get(CONF_SSL_KEY)
    cors_origins = conf.get(CONF_CORS_ORIGINS, [])
    approved_ips = conf.get(CONF_APPROVED_IPS, [])

    server = HomeAssistantWSGI(
        hass,
        development=development,
        server_host=server_host,
        server_port=server_port,
        api_password=api_password,
        ssl_certificate=ssl_certificate,
        ssl_key=ssl_key,
        cors_origins=cors_origins,
        approved_ips=approved_ips
    )

    def start_wsgi_server(event):
        """Start the WSGI server."""
        server.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_wsgi_server)

    def stop_wsgi_server(event):
        """Stop the WSGI server."""
        server.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_wsgi_server)

    hass.wsgi = server
    hass.config.api = rem.API(server_host if server_host != '0.0.0.0'
                              else util.get_local_ip(),
                              api_password, server_port,
                              ssl_certificate is not None)

    return True


def request_class():
    """Generate request class.

    Done in method because of imports.
    """
    from werkzeug.exceptions import BadRequest
    from werkzeug.wrappers import BaseRequest, AcceptMixin
    from werkzeug.utils import cached_property

    class Request(BaseRequest, AcceptMixin):
        """Base class for incoming requests."""

        @cached_property
        def json(self):
            """Get the result of json.loads if possible."""
            if not self.data:
                return None
            # elif 'json' not in self.environ.get('CONTENT_TYPE', ''):
            #     raise BadRequest('Not a JSON request')
            try:
                return json.loads(self.data.decode(
                    self.charset, self.encoding_errors))
            except (TypeError, ValueError):
                raise BadRequest('Unable to read JSON request')

    return Request


def routing_map(hass):
    """Generate empty routing map with HA validators."""
    from werkzeug.routing import Map, BaseConverter, ValidationError

    class EntityValidator(BaseConverter):
        """Validate entity_id in urls."""

        regex = r"(\w+)\.(\w+)"

        def __init__(self, url_map, exist=True, domain=None):
            """Initilalize entity validator."""
            super().__init__(url_map)
            self._exist = exist
            self._domain = domain

        def to_python(self, value):
            """Validate entity id."""
            if self._exist and hass.states.get(value) is None:
                raise ValidationError()
            if self._domain is not None and \
               split_entity_id(value)[0] != self._domain:
                raise ValidationError()

            return value

        def to_url(self, value):
            """Convert entity_id for a url."""
            return value

    class DateValidator(BaseConverter):
        """Validate dates in urls."""

        regex = r'\d{4}-\d{1,2}-\d{1,2}'

        def to_python(self, value):
            """Validate and convert date."""
            parsed = dt_util.parse_date(value)

            if parsed is None:
                raise ValidationError()

            return parsed

        def to_url(self, value):
            """Convert date to url value."""
            return value.isoformat()

    class DateTimeValidator(BaseConverter):
        """Validate datetimes in urls formatted per ISO 8601."""

        regex = r'\d{4}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d' \
            r'\.\d+([+-][0-2]\d:[0-5]\d|Z)'

        def to_python(self, value):
            """Validate and convert date."""
            parsed = dt_util.parse_datetime(value)

            if parsed is None:
                raise ValidationError()

            return parsed

        def to_url(self, value):
            """Convert date to url value."""
            return value.isoformat()

    return Map(converters={
        'entity': EntityValidator,
        'date': DateValidator,
        'datetime': DateTimeValidator,
    })


class HomeAssistantWSGI(object):
    """WSGI server for Home Assistant."""

    # pylint: disable=too-many-instance-attributes, too-many-locals
    # pylint: disable=too-many-arguments

    def __init__(self, hass, development, api_password, ssl_certificate,
                 ssl_key, server_host, server_port, cors_origins,
                 approved_ips):
        """Initilalize the WSGI Home Assistant server."""
        from werkzeug.wrappers import Response

        Response.mimetype = 'text/html'

        # pylint: disable=invalid-name
        self.Request = request_class()
        self.url_map = routing_map(hass)
        self.views = {}
        self.hass = hass
        self.extra_apps = {}
        self.development = development
        self.api_password = api_password
        self.ssl_certificate = ssl_certificate
        self.ssl_key = ssl_key
        self.server_host = server_host
        self.server_port = server_port
        self.cors_origins = cors_origins
        self.approved_ips = approved_ips
        self.event_forwarder = None
        self.server = None

    def register_view(self, view):
        """Register a view with the WSGI server.

        The view argument must be a class that inherits from HomeAssistantView.
        It is optional to instantiate it before registering; this method will
        handle it either way.
        """
        from werkzeug.routing import Rule

        if view.name in self.views:
            _LOGGER.warning("View '%s' is being overwritten", view.name)
        if isinstance(view, type):
            # Instantiate the view, if needed
            view = view(self.hass)

        self.views[view.name] = view

        rule = Rule(view.url, endpoint=view.name)
        self.url_map.add(rule)
        for url in view.extra_urls:
            rule = Rule(url, endpoint=view.name)
            self.url_map.add(rule)

    def register_redirect(self, url, redirect_to):
        """Register a redirect with the server.

        If given this must be either a string or callable. In case of a
        callable it's called with the url adapter that triggered the match and
        the values of the URL as keyword arguments and has to return the target
        for the redirect, otherwise it has to be a string with placeholders in
        rule syntax.
        """
        from werkzeug.routing import Rule

        self.url_map.add(Rule(url, redirect_to=redirect_to))

    def register_static_path(self, url_root, path, cache_length=31):
        """Register a folder to serve as a static path.

        Specify optional cache length of asset in days.
        """
        from static import Cling

        headers = []

        if cache_length and not self.development:
            # 1 year in seconds
            cache_time = cache_length * 86400

            headers.append({
                'prefix': '',
                HTTP_HEADER_CACHE_CONTROL:
                "public, max-age={}".format(cache_time)
            })

        self.register_wsgi_app(url_root, Cling(path, headers=headers))

    def register_wsgi_app(self, url_root, app):
        """Register a path to serve a WSGI app."""
        if url_root in self.extra_apps:
            _LOGGER.warning("Url root '%s' is being overwritten", url_root)

        self.extra_apps[url_root] = app

    def start(self):
        """Start the wsgi server."""
        from cherrypy import wsgiserver
        from cherrypy.wsgiserver.ssl_builtin import BuiltinSSLAdapter

        # pylint: disable=too-few-public-methods,super-init-not-called
        class ContextSSLAdapter(BuiltinSSLAdapter):
            """SSL Adapter that takes in an SSL context."""

            def __init__(self, context):
                self.context = context

        # pylint: disable=no-member
        self.server = wsgiserver.CherryPyWSGIServer(
            (self.server_host, self.server_port), self,
            server_name='Home Assistant')

        if self.ssl_certificate:
            context = ssl.SSLContext(SSL_VERSION)
            context.options |= SSL_OPTS
            context.set_ciphers(CIPHERS)
            context.load_cert_chain(self.ssl_certificate, self.ssl_key)
            self.server.ssl_adapter = ContextSSLAdapter(context)

        threading.Thread(target=self.server.start, daemon=True,
                         name='WSGI-server').start()

    def stop(self):
        """Stop the wsgi server."""
        self.server.stop()

    def dispatch_request(self, request):
        """Handle incoming request."""
        from werkzeug.exceptions import (
            MethodNotAllowed, NotFound, BadRequest, Unauthorized,
        )
        from werkzeug.routing import RequestRedirect

        with request:
            adapter = self.url_map.bind_to_environ(request.environ)
            try:
                endpoint, values = adapter.match()
                return self.views[endpoint].handle_request(request, **values)
            except RequestRedirect as ex:
                return ex
            except (BadRequest, NotFound, MethodNotAllowed,
                    Unauthorized) as ex:
                resp = ex.get_response(request.environ)
                if request.accept_mimetypes.accept_json:
                    resp.data = json.dumps({
                        "result": "error",
                        "message": str(ex),
                    })
                    resp.mimetype = "application/json"
                return resp

    def base_app(self, environ, start_response):
        """WSGI Handler of requests to base app."""
        request = self.Request(environ)
        response = self.dispatch_request(request)

        if self.cors_origins:
            cors_check = (environ.get("HTTP_ORIGIN") in self.cors_origins)
            cors_headers = ", ".join(ALLOWED_CORS_HEADERS)
            if cors_check:
                response.headers[HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN] = \
                    environ.get("HTTP_ORIGIN")
                response.headers[HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS] = \
                    cors_headers

        return response(environ, start_response)

    def __call__(self, environ, start_response):
        """Handle a request for base app + extra apps."""
        from werkzeug.wsgi import DispatcherMiddleware

        if not self.hass.is_running:
            from werkzeug.exceptions import BadRequest
            return BadRequest()(environ, start_response)

        app = DispatcherMiddleware(self.base_app, self.extra_apps)
        # Strip out any cachebusting MD5 fingerprints
        fingerprinted = _FINGERPRINT.match(environ.get('PATH_INFO', ''))
        if fingerprinted:
            environ['PATH_INFO'] = "{}.{}".format(*fingerprinted.groups())
        return app(environ, start_response)


class HomeAssistantView(object):
    """Base view for all views."""

    extra_urls = []
    requires_auth = True  # Views inheriting from this class can override this

    def __init__(self, hass):
        """Initilalize the base view."""
        from werkzeug.wrappers import Response

        if not hasattr(self, 'url'):
            class_name = self.__class__.__name__
            raise AttributeError(
                '{0} missing required attribute "url"'.format(class_name)
            )

        if not hasattr(self, 'name'):
            class_name = self.__class__.__name__
            raise AttributeError(
                '{0} missing required attribute "name"'.format(class_name)
            )

        self.hass = hass
        # pylint: disable=invalid-name
        self.Response = Response

    def handle_request(self, request, **values):
        """Handle request to url."""
        from werkzeug.exceptions import MethodNotAllowed, Unauthorized

        if request.method == "OPTIONS":
            # For CORS preflight requests.
            return self.options(request)

        try:
            handler = getattr(self, request.method.lower())
        except AttributeError:
            raise MethodNotAllowed

        # Auth code verbose on purpose
        authenticated = False

        if self.hass.wsgi.api_password is None:
            authenticated = True

        elif request.remote_addr in self.hass.wsgi.approved_ips:
            authenticated = True

        elif hmac.compare_digest(request.headers.get(HTTP_HEADER_HA_AUTH, ''),
                                 self.hass.wsgi.api_password):
            # A valid auth header has been set
            authenticated = True

        elif hmac.compare_digest(request.args.get(DATA_API_PASSWORD, ''),
                                 self.hass.wsgi.api_password):
            authenticated = True

        if self.requires_auth and not authenticated:
            _LOGGER.warning('Login attempt or request with an invalid '
                            'password from %s', request.remote_addr)
            raise Unauthorized()

        request.authenticated = authenticated

        _LOGGER.info('Serving %s to %s (auth: %s)',
                     request.path, request.remote_addr, authenticated)

        result = handler(request, **values)

        if isinstance(result, self.Response):
            # The method handler returned a ready-made Response, how nice of it
            return result

        status_code = 200

        if isinstance(result, tuple):
            result, status_code = result

        return self.Response(result, status=status_code)

    def json(self, result, status_code=200):
        """Return a JSON response."""
        msg = json.dumps(
            result,
            sort_keys=True,
            cls=rem.JSONEncoder
        ).encode('UTF-8')
        return self.Response(msg, mimetype="application/json",
                             status=status_code)

    def json_message(self, error, status_code=200):
        """Return a JSON message response."""
        return self.json({'message': error}, status_code)

    def file(self, request, fil, mimetype=None):
        """Return a file."""
        from werkzeug.wsgi import wrap_file
        from werkzeug.exceptions import NotFound

        if isinstance(fil, str):
            if mimetype is None:
                mimetype = mimetypes.guess_type(fil)[0]

            try:
                fil = open(fil, mode='br')
            except IOError:
                raise NotFound()

        return self.Response(wrap_file(request.environ, fil),
                             mimetype=mimetype, direct_passthrough=True)

    def options(self, request):
        """Default handler for OPTIONS (necessary for CORS preflight)."""
        return self.Response('', status=200)
