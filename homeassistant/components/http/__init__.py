"""
This module provides WSGI application to serve the Home Assistant API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/http/
"""
from ipaddress import ip_network
import logging
import os
import ssl

from aiohttp import web
from aiohttp.web_exceptions import HTTPMovedPermanently
import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, SERVER_PORT)
import homeassistant.helpers.config_validation as cv
import homeassistant.remote as rem
import homeassistant.util as hass_util
from homeassistant.util.logging import HideSensitiveDataFilter
from homeassistant.util import ssl as ssl_util

from .auth import setup_auth
from .ban import setup_bans
from .cors import setup_cors
from .real_ip import setup_real_ip
from .static import (
    CachingFileResponse, CachingStaticResource, staticresource_middleware)

# Import as alias
from .const import KEY_AUTHENTICATED, KEY_REAL_IP  # noqa
from .view import HomeAssistantView  # noqa

REQUIREMENTS = ['aiohttp_cors==0.7.0']

DOMAIN = 'http'

CONF_API_PASSWORD = 'api_password'
CONF_SERVER_HOST = 'server_host'
CONF_SERVER_PORT = 'server_port'
CONF_BASE_URL = 'base_url'
CONF_SSL_CERTIFICATE = 'ssl_certificate'
CONF_SSL_PEER_CERTIFICATE = 'ssl_peer_certificate'
CONF_SSL_KEY = 'ssl_key'
CONF_CORS_ORIGINS = 'cors_allowed_origins'
CONF_USE_X_FORWARDED_FOR = 'use_x_forwarded_for'
CONF_TRUSTED_PROXIES = 'trusted_proxies'
CONF_TRUSTED_NETWORKS = 'trusted_networks'
CONF_LOGIN_ATTEMPTS_THRESHOLD = 'login_attempts_threshold'
CONF_IP_BAN_ENABLED = 'ip_ban_enabled'

_LOGGER = logging.getLogger(__name__)

DEFAULT_SERVER_HOST = '0.0.0.0'
DEFAULT_DEVELOPMENT = '0'
NO_LOGIN_ATTEMPT_THRESHOLD = -1

HTTP_SCHEMA = vol.Schema({
    vol.Optional(CONF_API_PASSWORD): cv.string,
    vol.Optional(CONF_SERVER_HOST, default=DEFAULT_SERVER_HOST): cv.string,
    vol.Optional(CONF_SERVER_PORT, default=SERVER_PORT): cv.port,
    vol.Optional(CONF_BASE_URL): cv.string,
    vol.Optional(CONF_SSL_CERTIFICATE): cv.isfile,
    vol.Optional(CONF_SSL_PEER_CERTIFICATE): cv.isfile,
    vol.Optional(CONF_SSL_KEY): cv.isfile,
    vol.Optional(CONF_CORS_ORIGINS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_USE_X_FORWARDED_FOR, default=False): cv.boolean,
    vol.Optional(CONF_TRUSTED_PROXIES, default=[]):
        vol.All(cv.ensure_list, [ip_network]),
    vol.Optional(CONF_TRUSTED_NETWORKS, default=[]):
        vol.All(cv.ensure_list, [ip_network]),
    vol.Optional(CONF_LOGIN_ATTEMPTS_THRESHOLD,
                 default=NO_LOGIN_ATTEMPT_THRESHOLD):
        vol.Any(cv.positive_int, NO_LOGIN_ATTEMPT_THRESHOLD),
    vol.Optional(CONF_IP_BAN_ENABLED, default=True): cv.boolean
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: HTTP_SCHEMA,
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the HTTP API and debug interface."""
    conf = config.get(DOMAIN)

    if conf is None:
        conf = HTTP_SCHEMA({})

    api_password = conf.get(CONF_API_PASSWORD)
    server_host = conf[CONF_SERVER_HOST]
    server_port = conf[CONF_SERVER_PORT]
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)
    ssl_peer_certificate = conf.get(CONF_SSL_PEER_CERTIFICATE)
    ssl_key = conf.get(CONF_SSL_KEY)
    cors_origins = conf[CONF_CORS_ORIGINS]
    use_x_forwarded_for = conf[CONF_USE_X_FORWARDED_FOR]
    trusted_proxies = conf[CONF_TRUSTED_PROXIES]
    trusted_networks = conf[CONF_TRUSTED_NETWORKS]
    is_ban_enabled = conf[CONF_IP_BAN_ENABLED]
    login_threshold = conf[CONF_LOGIN_ATTEMPTS_THRESHOLD]

    if api_password is not None:
        logging.getLogger('aiohttp.access').addFilter(
            HideSensitiveDataFilter(api_password))

    server = HomeAssistantHTTP(
        hass,
        server_host=server_host,
        server_port=server_port,
        api_password=api_password,
        ssl_certificate=ssl_certificate,
        ssl_peer_certificate=ssl_peer_certificate,
        ssl_key=ssl_key,
        cors_origins=cors_origins,
        use_x_forwarded_for=use_x_forwarded_for,
        trusted_proxies=trusted_proxies,
        trusted_networks=trusted_networks,
        login_threshold=login_threshold,
        is_ban_enabled=is_ban_enabled
    )

    async def stop_server(event):
        """Stop the server."""
        await server.stop()

    async def start_server(event):
        """Start the server."""
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_server)
        await server.start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_server)

    hass.http = server

    host = conf.get(CONF_BASE_URL)

    if host:
        port = None
    elif server_host != DEFAULT_SERVER_HOST:
        host = server_host
        port = server_port
    else:
        host = hass_util.get_local_ip()
        port = server_port

    hass.config.api = rem.API(host, api_password, port,
                              ssl_certificate is not None)

    return True


class HomeAssistantHTTP:
    """HTTP server for Home Assistant."""

    def __init__(self, hass, api_password,
                 ssl_certificate, ssl_peer_certificate,
                 ssl_key, server_host, server_port, cors_origins,
                 use_x_forwarded_for, trusted_proxies, trusted_networks,
                 login_threshold, is_ban_enabled):
        """Initialize the HTTP Home Assistant server."""
        app = self.app = web.Application(
            middlewares=[staticresource_middleware])

        # This order matters
        setup_real_ip(app, use_x_forwarded_for, trusted_proxies)

        if is_ban_enabled:
            setup_bans(hass, app, login_threshold)

        if hass.auth.active:
            if hass.auth.support_legacy:
                _LOGGER.warning("Experimental auth api enabled and "
                                "legacy_api_password support enabled. Please "
                                "use access_token instead api_password, "
                                "although you can still use legacy "
                                "api_password")
            else:
                _LOGGER.warning("Experimental auth api enabled. Please use "
                                "access_token instead api_password.")
        elif api_password is None:
            _LOGGER.warning("You have been advised to set http.api_password.")

        setup_auth(app, trusted_networks, hass.auth.active,
                   support_legacy=hass.auth.support_legacy,
                   api_password=api_password)

        setup_cors(app, cors_origins)

        app['hass'] = hass

        self.hass = hass
        self.api_password = api_password
        self.ssl_certificate = ssl_certificate
        self.ssl_peer_certificate = ssl_peer_certificate
        self.ssl_key = ssl_key
        self.server_host = server_host
        self.server_port = server_port
        self.is_ban_enabled = is_ban_enabled
        self._handler = None
        self.server = None

    def register_view(self, view):
        """Register a view with the WSGI server.

        The view argument must be a class that inherits from HomeAssistantView.
        It is optional to instantiate it before registering; this method will
        handle it either way.
        """
        if isinstance(view, type):
            # Instantiate the view, if needed
            view = view()

        if not hasattr(view, 'url'):
            class_name = view.__class__.__name__
            raise AttributeError(
                '{0} missing required attribute "url"'.format(class_name)
            )

        if not hasattr(view, 'name'):
            class_name = view.__class__.__name__
            raise AttributeError(
                '{0} missing required attribute "name"'.format(class_name)
            )

        view.register(self.app, self.app.router)

    def register_redirect(self, url, redirect_to):
        """Register a redirect with the server.

        If given this must be either a string or callable. In case of a
        callable it's called with the url adapter that triggered the match and
        the values of the URL as keyword arguments and has to return the target
        for the redirect, otherwise it has to be a string with placeholders in
        rule syntax.
        """
        def redirect(request):
            """Redirect to location."""
            raise HTTPMovedPermanently(redirect_to)

        self.app.router.add_route('GET', url, redirect)

    def register_static_path(self, url_path, path, cache_headers=True):
        """Register a folder or file to serve as a static path."""
        if os.path.isdir(path):
            if cache_headers:
                resource = CachingStaticResource
            else:
                resource = web.StaticResource
            self.app.router.register_resource(resource(url_path, path))
            return

        if cache_headers:
            async def serve_file(request):
                """Serve file from disk."""
                return CachingFileResponse(path)
        else:
            async def serve_file(request):
                """Serve file from disk."""
                return web.FileResponse(path)

        # aiohttp supports regex matching for variables. Using that as temp
        # to work around cache busting MD5.
        # Turns something like /static/dev-panel.html into
        # /static/{filename:dev-panel(-[a-z0-9]{32}|)\.html}
        base, ext = os.path.splitext(url_path)
        if ext:
            base, file = base.rsplit('/', 1)
            regex = r"{}(-[a-z0-9]{{32}}|){}".format(file, ext)
            url_pattern = "{}/{{filename:{}}}".format(base, regex)
        else:
            url_pattern = url_path

        self.app.router.add_route('GET', url_pattern, serve_file)

    async def start(self):
        """Start the WSGI server."""
        # We misunderstood the startup signal. You're not allowed to change
        # anything during startup. Temp workaround.
        # pylint: disable=protected-access
        self.app._on_startup.freeze()
        await self.app.startup()

        if self.ssl_certificate:
            try:
                context = ssl_util.server_context()
                context.load_cert_chain(self.ssl_certificate, self.ssl_key)
            except OSError as error:
                _LOGGER.error("Could not read SSL certificate from %s: %s",
                              self.ssl_certificate, error)
                return

            if self.ssl_peer_certificate:
                context.verify_mode = ssl.CERT_REQUIRED
                context.load_verify_locations(cafile=self.ssl_peer_certificate)

        else:
            context = None

        # Aiohttp freezes apps after start so that no changes can be made.
        # However in Home Assistant components can be discovered after boot.
        # This will now raise a RunTimeError.
        # To work around this we now prevent the router from getting frozen
        self.app._router.freeze = lambda: None

        self._handler = self.app.make_handler(loop=self.hass.loop)

        try:
            self.server = await self.hass.loop.create_server(
                self._handler, self.server_host, self.server_port, ssl=context)
        except OSError as error:
            _LOGGER.error("Failed to create HTTP server at port %d: %s",
                          self.server_port, error)

    async def stop(self):
        """Stop the WSGI server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await self.app.shutdown()
        if self._handler:
            await self._handler.shutdown(10)
        await self.app.cleanup()
