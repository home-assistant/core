"""
This module provides WSGI application to serve the Home Assistant API.

"""
import json
import logging
import threading
import re

import homeassistant.core as ha
import homeassistant.remote as rem
from homeassistant import util
from homeassistant.const import (
    SERVER_PORT, HTTP_OK, HTTP_NOT_FOUND, HTTP_BAD_REQUEST
)

DOMAIN = "wsgi"
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

    server = HomeAssistantWSGI(
        hass,
        development=str(conf.get(CONF_DEVELOPMENT, "")) == "1",
        server_host=conf.get(CONF_SERVER_HOST, '0.0.0.0'),
        server_port=conf.get(CONF_SERVER_PORT, SERVER_PORT),
        api_password=util.convert(conf.get(CONF_API_PASSWORD), str),
        ssl_certificate=conf.get(CONF_SSL_CERTIFICATE),
        ssl_key=conf.get(CONF_SSL_KEY),
    )

    hass.bus.listen_once(
        ha.EVENT_HOMEASSISTANT_START,
        lambda event:
        threading.Thread(target=server.start, daemon=True,
                         name='WSGI-server').start())

    hass.wsgi = server

    return True


class StaticFileServer(object):
    def __call__(self, environ, start_response):
        from werkzeug.wsgi import DispatcherMiddleware
        app = DispatcherMiddleware(self.base_app, self.extra_apps)
        # Strip out any cachebusting MD% fingerprints
        fingerprinted = _FINGERPRINT.match(environ['PATH_INFO'])
        if fingerprinted:
            environ['PATH_INFO'] = "{}.{}".format(*fingerprinted.groups())
        return app(environ, start_response)


class HomeAssistantWSGI(object):
    def __init__(self, hass, development, api_password, ssl_certificate,
                 ssl_key, server_host, server_port):
        from werkzeug.wrappers import BaseRequest, AcceptMixin
        from werkzeug.routing import Map

        class Request(BaseRequest, AcceptMixin):
            pass

        self.Request = Request
        self.url_map = Map()
        self.views = {}
        self.hass = hass
        self.extra_apps = {}
        self.development = development
        self.api_password = api_password
        self.ssl_certificate = ssl_certificate
        self.ssl_key = ssl_key

    def register_view(self, view):
        """ Register a view with the WSGI server.

        The view argument must inherit from the HomeAssistantView class, and
        it must have (globally unique) 'url' and 'name' attributes.
        """
        from werkzeug.routing import Rule

        if view.name in self.views:
            _LOGGER.warning("View '{}' is being overwritten".format(view.name))
        self.views[view.name] = view(self.hass)
        # TODO Warn if we're overriding an existing view
        rule = Rule(view.url, endpoint=view.name)
        self.url_map.add(rule)
        for url in view.extra_urls:
            rule = Rule(url, endpoint=view.name)
            self.url_map.add(rule)

    def register_static_path(self, url_root, path):
        """Register a folder to serve as a static path."""
        from static import Cling

        # TODO Warn if we're overwriting an existing path
        self.extra_apps[url_root] = Cling(path)

    def start(self):
        """Start the wsgi server."""
        from eventlet import wsgi
        import eventlet

        sock = eventlet.listen(('', 8090))
        if self.ssl_certificate:
            eventlet.wrap_ssl(sock, certfile=self.ssl_certificate,
                              keyfile=self.ssl_key, server_side=True)
        wsgi.server(sock, self)

    def dispatch_request(self, request):
        """Handle incoming request."""
        from werkzeug.exceptions import (
            MethodNotAllowed, NotFound, BadRequest, Unauthorized
        )
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return self.views[endpoint].handle_request(request, **values)
        except BadRequest as e:
            return self.handle_error(request, str(e), HTTP_BAD_REQUEST)
        except NotFound as e:
            return self.handle_error(request, str(e), HTTP_NOT_FOUND)
        except MethodNotAllowed as e:
            return self.handle_error(request, str(e), 405)
        except Unauthorized as e:
            return self.handle_error(request, str(e), 401)
        # TODO This long chain of except blocks is silly. _handle_error should
        # just take the exception as an argument and parse the status code
        # itself

    def base_app(self, environ, start_response):
        request = self.Request(environ)
        request.api_password = self.api_password
        request.development = self.development
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        from werkzeug.wsgi import DispatcherMiddleware

        app = DispatcherMiddleware(self.base_app, self.extra_apps)
        # Strip out any cachebusting MD5 fingerprints
        fingerprinted = _FINGERPRINT.match(environ.get('PATH_INFO', ''))
        if fingerprinted:
            environ['PATH_INFO'] = "{}.{}".format(*fingerprinted.groups())
        return app(environ, start_response)

    def _handle_error(self, request, message, status):
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
    extra_urls = []
    requires_auth = True  # Views inheriting from this class can override this

    def __init__(self, hass):
        from werkzeug.wrappers import Response
        from werkzeug.exceptions import NotFound, BadRequest

        self.hass = hass
        self.Response = Response
        self.NotFound = NotFound
        self.BadRequest = BadRequest

    def handle_request(self, request, **values):
        """Handle request to url."""
        from werkzeug.exceptions import MethodNotAllowed

        try:
            handler = getattr(self, request.method.lower())
        except AttributeError:
            raise MethodNotAllowed
        # TODO This would be a good place to check the auth if
        # self.requires_auth is true, and raise Unauthorized on a failure
        result = handler(request, **values)
        if isinstance(result, self.Response):
            # The method handler returned a ready-made Response, how nice of it
            return result
        elif (isinstance(result, dict) or
              isinstance(result, list) or
              isinstance(result, ha.State)):
            # There are a few result types we know we always want to jsonify
            if isinstance(result, dict) and 'status_code' in result:
                status_code = result['status_code']
                del result['status_code']
            else:
                status_code = HTTP_OK
            msg = json.dumps(
                result,
                sort_keys=True,
                cls=rem.JSONEncoder
            ).encode('UTF-8')
            return self.Response(msg, mimetype="application/json",
                                 status_code=status_code)
