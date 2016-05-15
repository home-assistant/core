"""This module provides WSGI application to serve the Home Assistant API."""
import hmac
import json
import logging
import mimetypes
import threading
import re

import homeassistant.core as ha
import homeassistant.remote as rem
from homeassistant import util
from homeassistant.const import SERVER_PORT, HTTP_HEADER_HA_AUTH

DOMAIN = "http"
REQUIREMENTS = ("eventlet==0.18.4", "static3==0.6.1", "Werkzeug==0.11.5",)

CONF_API_PASSWORD = "api_password"
CONF_SERVER_HOST = "server_host"
CONF_SERVER_PORT = "server_port"
CONF_DEVELOPMENT = "development"
CONF_SSL_CERTIFICATE = 'ssl_certificate'
CONF_SSL_KEY = 'ssl_key'

DATA_API_PASSWORD = 'api_password'

_FINGERPRINT = re.compile(r'^(.+)-[a-z0-9]{32}\.(\w+)$', re.IGNORECASE)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Set up the HTTP API and debug interface."""
    conf = config.get(DOMAIN, {})

    api_password = util.convert(conf.get(CONF_API_PASSWORD), str)
    server_host = conf.get(CONF_SERVER_HOST, '0.0.0.0')
    server_port = conf.get(CONF_SERVER_PORT, SERVER_PORT)
    development = str(conf.get(CONF_DEVELOPMENT, "")) == "1"
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)
    ssl_key = conf.get(CONF_SSL_KEY)

    server = HomeAssistantWSGI(
        hass,
        development=development,
        server_host=server_host,
        server_port=server_port,
        api_password=api_password,
        ssl_certificate=ssl_certificate,
        ssl_key=ssl_key,
    )

    hass.bus.listen_once(
        ha.EVENT_HOMEASSISTANT_START,
        lambda event:
        threading.Thread(target=server.start, daemon=True,
                         name='WSGI-server').start())

    hass.wsgi = server
    hass.config.api = rem.API(server_host if server_host != '0.0.0.0'
                              else util.get_local_ip(),
                              api_password, server_port,
                              ssl_certificate is not None)

    return True


# class StaticFileServer(object):
#     """Static file serving middleware."""

#     def __call__(self, environ, start_response):
#         from werkzeug.wsgi import DispatcherMiddleware
#         app = DispatcherMiddleware(self.base_app, self.extra_apps)
#         # Strip out any cachebusting MD% fingerprints
#         fingerprinted = _FINGERPRINT.match(environ['PATH_INFO'])
#         if fingerprinted:
#             environ['PATH_INFO'] = "{}.{}".format(*fingerprinted.groups())
#         return app(environ, start_response)


class HomeAssistantWSGI(object):
    """WSGI server for Home Assistant."""

    # pylint: disable=too-many-instance-attributes, too-many-locals
    # pylint: disable=too-many-arguments

    def __init__(self, hass, development, api_password, ssl_certificate,
                 ssl_key, server_host, server_port):
        """Initilalize the WSGI Home Assistant server."""
        from werkzeug.exceptions import BadRequest
        from werkzeug.wrappers import BaseRequest, AcceptMixin
        from werkzeug.routing import Map
        from werkzeug.utils import cached_property
        from werkzeug.wrappers import Response

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

        Response.mimetype = 'text/html'

        # pylint: disable=invalid-name
        self.Request = Request
        self.url_map = Map()
        self.views = {}
        self.hass = hass
        self.extra_apps = {}
        self.development = development
        self.api_password = api_password
        self.ssl_certificate = ssl_certificate
        self.ssl_key = ssl_key
        self.server_host = server_host
        self.server_port = server_port
        self.event_forwarder = None

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
        callable it’s called with the url adapter that triggered the match and
        the values of the URL as keyword arguments and has to return the target
        for the redirect, otherwise it has to be a string with placeholders in
        rule syntax.
        """
        from werkzeug.routing import Rule

        self.url_map.add(Rule(url, redirect_to=redirect_to))

    def register_static_path(self, url_root, path):
        """Register a folder to serve as a static path."""
        from static import Cling

        if url_root in self.extra_apps:
            _LOGGER.warning("Static path '%s' is being overwritten", path)
        self.extra_apps[url_root] = Cling(path)

    def start(self):
        """Start the wsgi server."""
        from eventlet import wsgi
        import eventlet

        sock = eventlet.listen((self.server_host, self.server_port))
        if self.ssl_certificate:
            eventlet.wrap_ssl(sock, certfile=self.ssl_certificate,
                              keyfile=self.ssl_key, server_side=True)
        wsgi.server(sock, self)

    def dispatch_request(self, request):
        """Handle incoming request."""
        from werkzeug.exceptions import (
            MethodNotAllowed, NotFound, BadRequest, Unauthorized,
        )
        from werkzeug.routing import RequestRedirect

        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return self.views[endpoint].handle_request(request, **values)
        except RequestRedirect as ex:
            return ex
        except BadRequest as ex:
            return self._handle_error(request, str(ex), 400)
        except NotFound as ex:
            return self._handle_error(request, str(ex), 404)
        except MethodNotAllowed as ex:
            return self._handle_error(request, str(ex), 405)
        except Unauthorized as ex:
            return self._handle_error(request, str(ex), 401)
        # TODO This long chain of except blocks is silly. _handle_error should
        # just take the exception as an argument and parse the status code
        # itself

    def base_app(self, environ, start_response):
        """WSGI Handler of requests to base app."""
        request = self.Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        """Handle a request for base app + extra apps."""
        from werkzeug.wsgi import DispatcherMiddleware

        app = DispatcherMiddleware(self.base_app, self.extra_apps)
        # Strip out any cachebusting MD5 fingerprints
        fingerprinted = _FINGERPRINT.match(environ.get('PATH_INFO', ''))
        if fingerprinted:
            environ['PATH_INFO'] = "{}.{}".format(*fingerprinted.groups())
        return app(environ, start_response)

    def _handle_error(self, request, message, status):
        """Handle a WSGI request error."""
        from werkzeug.wrappers import Response
        if request.accept_mimetypes.accept_json:
            message = json.dumps({
                "result": "error",
                "message": message,
            })
            mimetype = "application/json"
        else:
            mimetype = "text/plain"
        return Response(message, status=status, mimetype=mimetype)


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
        from werkzeug.exceptions import (
            MethodNotAllowed, Unauthorized, BadRequest,
        )

        try:
            handler = getattr(self, request.method.lower())
        except AttributeError:
            raise MethodNotAllowed

        # TODO: session support + uncomment session test

        # Auth code verbose on purpose
        authenticated = False

        if not self.requires_auth:
            authenticated = True

        elif self.hass.wsgi.api_password is None:
            authenticated = True

        elif hmac.compare_digest(request.headers.get(HTTP_HEADER_HA_AUTH, ''),
                                 self.hass.wsgi.api_password):
            # A valid auth header has been set
            authenticated = True

        elif hmac.compare_digest(request.args.get(DATA_API_PASSWORD, ''),
                                 self.hass.wsgi.api_password):
            authenticated = True

        else:
            # Do we still want to support passing it in as post data?
            try:
                json_data = request.json
                if (json_data is not None and
                        hmac.compare_digest(
                            json_data.get(DATA_API_PASSWORD, ''),
                            self.hass.wsgi.api_password)):
                    authenticated = True
            except BadRequest:
                pass

        if not authenticated:
            raise Unauthorized()

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
            try:
                fil = open(fil)
            except IOError:
                raise NotFound()

            if mimetype is None:
                mimetype = mimetypes.guess_type(fil)[0]

        return self.Response(wrap_file(request.environ, fil),
                             mimetype=mimetype, direct_passthrough=True)
