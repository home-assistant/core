"""
This module provides WSGI application to serve the Home Assistant API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/http/
"""
from ipaddress import ip_network
import logging
import os
import ssl
from typing import Optional

from aiohttp import web
from aiohttp.web_exceptions import HTTPMovedPermanently
import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, SERVER_PORT)
import homeassistant.helpers.config_validation as cv
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
CONF_SSL_PROFILE = 'ssl_profile'

SSL_MODERN = 'modern'
SSL_INTERMEDIATE = 'intermediate'

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
    vol.Inclusive(CONF_USE_X_FORWARDED_FOR, 'proxy'): cv.boolean,
    vol.Inclusive(CONF_TRUSTED_PROXIES, 'proxy'):
        vol.All(cv.ensure_list, [ip_network]),
    vol.Optional(CONF_TRUSTED_NETWORKS, default=[]):
        vol.All(cv.ensure_list, [ip_network]),
    vol.Optional(CONF_LOGIN_ATTEMPTS_THRESHOLD,
                 default=NO_LOGIN_ATTEMPT_THRESHOLD):
        vol.Any(cv.positive_int, NO_LOGIN_ATTEMPT_THRESHOLD),
    vol.Optional(CONF_IP_BAN_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_SSL_PROFILE, default=SSL_MODERN):
        vol.In([SSL_INTERMEDIATE, SSL_MODERN]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: HTTP_SCHEMA,
}, extra=vol.ALLOW_EXTRA)


class ApiConfig:
    """Configuration settings for API server."""

    def __init__(self, host: str, port: Optional[int] = SERVER_PORT,
                 use_ssl: bool = False,
                 api_password: Optional[str] = None) -> None:
        """Initialize a new API config object."""
        self.host = host
        self.port = port
        self.api_password = api_password

        if host.startswith(("http://", "https://")):
            self.base_url = host
        elif use_ssl:
            self.base_url = "https://{}".format(host)
        else:
            self.base_url = "http://{}".format(host)

        if port is not None:
            self.base_url += ':{}'.format(port)


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
    use_x_forwarded_for = conf.get(CONF_USE_X_FORWARDED_FOR, False)
    trusted_proxies = conf.get(CONF_TRUSTED_PROXIES, [])
    trusted_networks = conf[CONF_TRUSTED_NETWORKS]
    is_ban_enabled = conf[CONF_IP_BAN_ENABLED]
    login_threshold = conf[CONF_LOGIN_ATTEMPTS_THRESHOLD]
    ssl_profile = conf[CONF_SSL_PROFILE]

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
        is_ban_enabled=is_ban_enabled,
        ssl_profile=ssl_profile,
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

    hass.config.api = ApiConfig(host, port, ssl_certificate is not None,
                                api_password)

    return True


class HomeAssistantHTTP:
    """HTTP server for Home Assistant."""

    def __init__(self, hass, api_password,
                 ssl_certificate, ssl_peer_certificate,
                 ssl_key, server_host, server_port, cors_origins,
                 use_x_forwarded_for, trusted_proxies, trusted_networks,
                 login_threshold, is_ban_enabled, ssl_profile):
        """Initialize the HTTP Home Assistant server."""
        app = self.app = web.Application(
            middlewares=[staticresource_middleware])

        # This order matters
        setup_real_ip(app, use_x_forwarded_for, trusted_proxies)

        if is_ban_enabled:
            setup_bans(hass, app, login_threshold)

        if hass.auth.support_legacy:
            _LOGGER.warning(
                "legacy_api_password support has been enabled. If you don't "
                "require it, remove the 'api_password' from your http config.")

        setup_auth(app, trusted_networks,
                   api_password if hass.auth.support_legacy else None)

        setup_cors(app, cors_origins)

        app['hass'] = hass

        self.hass = hass
        self.api_password = api_password
        self.ssl_certificate = ssl_certificate
        self.ssl_peer_certificate = ssl_peer_certificate
        self.ssl_key = ssl_key
        self.server_host = server_host
        self.server_port = server_port
        self.trusted_networks = trusted_networks
        self.is_ban_enabled = is_ban_enabled
        self.ssl_profile = ssl_profile
        self._handler = None
        self.runner = None
        self.site = None

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
        """Start the aiohttp server."""
        if self.ssl_certificate:
            try:
                if self.ssl_profile == SSL_INTERMEDIATE:
                    context = ssl_util.server_context_intermediate()
                else:
                    context = ssl_util.server_context_modern()
                await self.hass.async_add_executor_job(
                    context.load_cert_chain, self.ssl_certificate,
                    self.ssl_key)
            except OSError as error:
                _LOGGER.error("Could not read SSL certificate from %s: %s",
                              self.ssl_certificate, error)
                return

            if self.ssl_peer_certificate:
                context.verify_mode = ssl.CERT_REQUIRED
                await self.hass.async_add_executor_job(
                    context.load_verify_locations,
                    self.ssl_peer_certificate)

        else:
            context = None

        # Aiohttp freezes apps after start so that no changes can be made.
        # However in Home Assistant components can be discovered after boot.
        # This will now raise a RunTimeError.
        # To work around this we now prevent the router from getting frozen
        # pylint: disable=protected-access
        self.app._router.freeze = lambda: None

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.server_host,
                                self.server_port, ssl_context=context)
        try:
            await self.site.start()
        except OSError as error:
            _LOGGER.error("Failed to create HTTP server at port %d: %s",
                          self.server_port, error)

    async def stop(self):
        """Stop the aiohttp server."""
        await self.site.stop()
        await self.runner.cleanup()
