"""Support to serve the Home Assistant API as WSGI application."""
from __future__ import annotations

from contextvars import ContextVar
from ipaddress import ip_network
import logging
import os
import ssl
from typing import Any, Final, Optional, TypedDict, cast

from aiohttp import web
from aiohttp.typedefs import StrOrURL
from aiohttp.web_exceptions import HTTPMovedPermanently, HTTPRedirection
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, SERVER_PORT
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import storage
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.setup import async_start_setup, async_when_setup_or_start
import homeassistant.util as hass_util
from homeassistant.util import ssl as ssl_util

from .auth import setup_auth
from .ban import setup_bans
from .const import KEY_AUTHENTICATED, KEY_HASS, KEY_HASS_USER  # noqa: F401
from .cors import setup_cors
from .forwarded import async_setup_forwarded
from .request_context import setup_request_context
from .security_filter import setup_security_filter
from .static import CACHE_HEADERS, CachingStaticResource
from .view import HomeAssistantView
from .web_runner import HomeAssistantTCPSite

DOMAIN: Final = "http"

CONF_SERVER_HOST: Final = "server_host"
CONF_SERVER_PORT: Final = "server_port"
CONF_BASE_URL: Final = "base_url"
CONF_SSL_CERTIFICATE: Final = "ssl_certificate"
CONF_SSL_PEER_CERTIFICATE: Final = "ssl_peer_certificate"
CONF_SSL_KEY: Final = "ssl_key"
CONF_CORS_ORIGINS: Final = "cors_allowed_origins"
CONF_USE_X_FORWARDED_FOR: Final = "use_x_forwarded_for"
CONF_TRUSTED_PROXIES: Final = "trusted_proxies"
CONF_LOGIN_ATTEMPTS_THRESHOLD: Final = "login_attempts_threshold"
CONF_IP_BAN_ENABLED: Final = "ip_ban_enabled"
CONF_SSL_PROFILE: Final = "ssl_profile"

SSL_MODERN: Final = "modern"
SSL_INTERMEDIATE: Final = "intermediate"

_LOGGER: Final = logging.getLogger(__name__)

DEFAULT_DEVELOPMENT: Final = "0"
# Cast to be able to load custom cards.
# My to be able to check url and version info.
DEFAULT_CORS: Final[list[str]] = ["https://cast.home-assistant.io"]
NO_LOGIN_ATTEMPT_THRESHOLD: Final = -1

MAX_CLIENT_SIZE: Final = 1024 ** 2 * 16

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1
SAVE_DELAY: Final = 180

HTTP_SCHEMA: Final = vol.All(
    cv.deprecated(CONF_BASE_URL),
    vol.Schema(
        {
            vol.Optional(CONF_SERVER_HOST): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
            vol.Optional(CONF_SERVER_PORT, default=SERVER_PORT): cv.port,
            vol.Optional(CONF_BASE_URL): cv.string,
            vol.Optional(CONF_SSL_CERTIFICATE): cv.isfile,
            vol.Optional(CONF_SSL_PEER_CERTIFICATE): cv.isfile,
            vol.Optional(CONF_SSL_KEY): cv.isfile,
            vol.Optional(CONF_CORS_ORIGINS, default=DEFAULT_CORS): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Inclusive(CONF_USE_X_FORWARDED_FOR, "proxy"): cv.boolean,
            vol.Inclusive(CONF_TRUSTED_PROXIES, "proxy"): vol.All(
                cv.ensure_list, [ip_network]
            ),
            vol.Optional(
                CONF_LOGIN_ATTEMPTS_THRESHOLD, default=NO_LOGIN_ATTEMPT_THRESHOLD
            ): vol.Any(cv.positive_int, NO_LOGIN_ATTEMPT_THRESHOLD),
            vol.Optional(CONF_IP_BAN_ENABLED, default=True): cv.boolean,
            vol.Optional(CONF_SSL_PROFILE, default=SSL_MODERN): vol.In(
                [SSL_INTERMEDIATE, SSL_MODERN]
            ),
        }
    ),
)

CONFIG_SCHEMA: Final = vol.Schema({DOMAIN: HTTP_SCHEMA}, extra=vol.ALLOW_EXTRA)


class ConfData(TypedDict, total=False):
    """Typed dict for config data."""

    server_host: list[str]
    server_port: int
    base_url: str
    ssl_certificate: str
    ssl_peer_certificate: str
    ssl_key: str
    cors_allowed_origins: list[str]
    use_x_forwarded_for: bool
    trusted_proxies: list[str]
    login_attempts_threshold: int
    ip_ban_enabled: bool
    ssl_profile: str


@bind_hass
async def async_get_last_config(hass: HomeAssistant) -> dict | None:
    """Return the last known working config."""
    store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
    return cast(Optional[dict], await store.async_load())


class ApiConfig:
    """Configuration settings for API server."""

    def __init__(
        self,
        local_ip: str,
        host: str,
        port: int,
        use_ssl: bool,
    ) -> None:
        """Initialize a new API config object."""
        self.local_ip = local_ip
        self.host = host
        self.port = port
        self.use_ssl = use_ssl


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HTTP API and debug interface."""
    conf: ConfData | None = config.get(DOMAIN)

    if conf is None:
        conf = cast(ConfData, HTTP_SCHEMA({}))

    server_host = conf.get(CONF_SERVER_HOST)
    server_port = conf[CONF_SERVER_PORT]
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)
    ssl_peer_certificate = conf.get(CONF_SSL_PEER_CERTIFICATE)
    ssl_key = conf.get(CONF_SSL_KEY)
    cors_origins = conf[CONF_CORS_ORIGINS]
    use_x_forwarded_for = conf.get(CONF_USE_X_FORWARDED_FOR, False)
    trusted_proxies = conf.get(CONF_TRUSTED_PROXIES) or []
    is_ban_enabled = conf[CONF_IP_BAN_ENABLED]
    login_threshold = conf[CONF_LOGIN_ATTEMPTS_THRESHOLD]
    ssl_profile = conf[CONF_SSL_PROFILE]

    server = HomeAssistantHTTP(
        hass,
        server_host=server_host,
        server_port=server_port,
        ssl_certificate=ssl_certificate,
        ssl_peer_certificate=ssl_peer_certificate,
        ssl_key=ssl_key,
        cors_origins=cors_origins,
        use_x_forwarded_for=use_x_forwarded_for,
        trusted_proxies=trusted_proxies,
        login_threshold=login_threshold,
        is_ban_enabled=is_ban_enabled,
        ssl_profile=ssl_profile,
    )

    async def stop_server(event: Event) -> None:
        """Stop the server."""
        await server.stop()

    async def start_server(*_: Any) -> None:
        """Start the server."""
        with async_start_setup(hass, ["http"]):
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_server)
            # We already checked it's not None.
            assert conf is not None
            await start_http_server_and_save_config(hass, dict(conf), server)

    async_when_setup_or_start(hass, "frontend", start_server)

    hass.http = server

    local_ip = await hass.async_add_executor_job(hass_util.get_local_ip)

    host = local_ip
    if server_host is not None:
        # Assume the first server host name provided as API host
        host = server_host[0]

    hass.config.api = ApiConfig(
        local_ip, host, server_port, ssl_certificate is not None
    )

    return True


class HomeAssistantHTTP:
    """HTTP server for Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        ssl_certificate: str | None,
        ssl_peer_certificate: str | None,
        ssl_key: str | None,
        server_host: list[str] | None,
        server_port: int,
        cors_origins: list[str],
        use_x_forwarded_for: bool,
        trusted_proxies: list[str],
        login_threshold: int,
        is_ban_enabled: bool,
        ssl_profile: str,
    ) -> None:
        """Initialize the HTTP Home Assistant server."""
        app = self.app = web.Application(
            middlewares=[], client_max_size=MAX_CLIENT_SIZE
        )
        app[KEY_HASS] = hass

        # Order matters, security filters middle ware needs to go first,
        # forwarded middleware needs to go second.
        setup_security_filter(app)

        async_setup_forwarded(app, use_x_forwarded_for, trusted_proxies)

        setup_request_context(app, current_request)

        if is_ban_enabled:
            setup_bans(hass, app, login_threshold)

        setup_auth(hass, app)

        setup_cors(app, cors_origins)

        self.hass = hass
        self.ssl_certificate = ssl_certificate
        self.ssl_peer_certificate = ssl_peer_certificate
        self.ssl_key = ssl_key
        self.server_host = server_host
        self.server_port = server_port
        self.trusted_proxies = trusted_proxies
        self.is_ban_enabled = is_ban_enabled
        self.ssl_profile = ssl_profile
        self._handler = None
        self.runner: web.AppRunner | None = None
        self.site: HomeAssistantTCPSite | None = None

    def register_view(self, view: HomeAssistantView) -> None:
        """Register a view with the WSGI server.

        The view argument must be a class that inherits from HomeAssistantView.
        It is optional to instantiate it before registering; this method will
        handle it either way.
        """
        if isinstance(view, type):
            # Instantiate the view, if needed
            view = view()

        if not hasattr(view, "url"):
            class_name = view.__class__.__name__
            raise AttributeError(f'{class_name} missing required attribute "url"')

        if not hasattr(view, "name"):
            class_name = view.__class__.__name__
            raise AttributeError(f'{class_name} missing required attribute "name"')

        view.register(self.app, self.app.router)

    def register_redirect(
        self,
        url: str,
        redirect_to: StrOrURL,
        *,
        redirect_exc: type[HTTPRedirection] = HTTPMovedPermanently,
    ) -> None:
        """Register a redirect with the server.

        If given this must be either a string or callable. In case of a
        callable it's called with the url adapter that triggered the match and
        the values of the URL as keyword arguments and has to return the target
        for the redirect, otherwise it has to be a string with placeholders in
        rule syntax.
        """

        async def redirect(request: web.Request) -> web.StreamResponse:
            """Redirect to location."""
            # Should be instance of aiohttp.web_exceptions._HTTPMove.
            raise redirect_exc(redirect_to)  # type: ignore[arg-type,misc]

        self.app.router.add_route("GET", url, redirect)

    def register_static_path(
        self, url_path: str, path: str, cache_headers: bool = True
    ) -> web.FileResponse | None:
        """Register a folder or file to serve as a static path."""
        if os.path.isdir(path):
            if cache_headers:
                resource: type[
                    CachingStaticResource | web.StaticResource
                ] = CachingStaticResource
            else:
                resource = web.StaticResource
            self.app.router.register_resource(resource(url_path, path))
            return None

        async def serve_file(request: web.Request) -> web.FileResponse:
            """Serve file from disk."""
            if cache_headers:
                return web.FileResponse(path, headers=CACHE_HEADERS)
            return web.FileResponse(path)

        self.app.router.add_route("GET", url_path, serve_file)
        return None

    async def start(self) -> None:
        """Start the aiohttp server."""
        context: ssl.SSLContext | None
        if self.ssl_certificate:
            try:
                if self.ssl_profile == SSL_INTERMEDIATE:
                    context = ssl_util.server_context_intermediate()
                else:
                    context = ssl_util.server_context_modern()
                await self.hass.async_add_executor_job(
                    context.load_cert_chain, self.ssl_certificate, self.ssl_key
                )
            except OSError as error:
                _LOGGER.error(
                    "Could not read SSL certificate from %s: %s",
                    self.ssl_certificate,
                    error,
                )
                return

            if self.ssl_peer_certificate:
                context.verify_mode = ssl.CERT_REQUIRED
                await self.hass.async_add_executor_job(
                    context.load_verify_locations, self.ssl_peer_certificate
                )

        else:
            context = None

        # Aiohttp freezes apps after start so that no changes can be made.
        # However in Home Assistant components can be discovered after boot.
        # This will now raise a RunTimeError.
        # To work around this we now prevent the router from getting frozen
        # pylint: disable=protected-access
        self.app._router.freeze = lambda: None  # type: ignore[assignment]

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = HomeAssistantTCPSite(
            self.runner, self.server_host, self.server_port, ssl_context=context
        )
        try:
            await self.site.start()
        except OSError as error:
            _LOGGER.error(
                "Failed to create HTTP server at port %d: %s", self.server_port, error
            )

        _LOGGER.info("Now listening on port %d", self.server_port)

    async def stop(self) -> None:
        """Stop the aiohttp server."""
        if self.site is not None:
            await self.site.stop()
        if self.runner is not None:
            await self.runner.cleanup()


async def start_http_server_and_save_config(
    hass: HomeAssistant, conf: dict, server: HomeAssistantHTTP
) -> None:
    """Startup the http server and save the config."""
    await server.start()

    # If we are set up successful, we store the HTTP settings for safe mode.
    store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)

    if CONF_TRUSTED_PROXIES in conf:
        conf[CONF_TRUSTED_PROXIES] = [
            str(ip.network_address) for ip in conf[CONF_TRUSTED_PROXIES]
        ]

    store.async_delay_save(lambda: conf, SAVE_DELAY)


current_request: ContextVar[web.Request | None] = ContextVar(
    "current_request", default=None
)
