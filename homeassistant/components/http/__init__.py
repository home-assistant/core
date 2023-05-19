"""Support to serve the Home Assistant API as WSGI application."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
from ipaddress import IPv4Network, IPv6Network, ip_network
import logging
import os
import ssl
from tempfile import NamedTemporaryFile
from typing import Any, Final, TypedDict, cast

from aiohttp import web
from aiohttp.abc import AbstractStreamWriter
from aiohttp.http_parser import RawRequestMessage
from aiohttp.streams import StreamReader
from aiohttp.typedefs import JSONDecoder, StrOrURL
from aiohttp.web_exceptions import HTTPMovedPermanently, HTTPRedirection
from aiohttp.web_log import AccessLogger
from aiohttp.web_protocol import RequestHandler
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import voluptuous as vol
from yarl import URL

from homeassistant.components.network import async_get_source_ip
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, SERVER_PORT
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import storage
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.setup import async_start_setup, async_when_setup_or_start
from homeassistant.util import ssl as ssl_util
from homeassistant.util.json import json_loads

from .auth import async_setup_auth
from .ban import setup_bans
from .const import (  # noqa: F401
    KEY_AUTHENTICATED,
    KEY_HASS,
    KEY_HASS_REFRESH_TOKEN_ID,
    KEY_HASS_USER,
)
from .cors import setup_cors
from .forwarded import async_setup_forwarded
from .request_context import current_request, setup_request_context
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

MAX_CLIENT_SIZE: Final = 1024**2 * 16
MAX_LINE_SIZE: Final = 24570

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1
SAVE_DELAY: Final = 180

CONF_SERVERS = "servers"

SERVER_SCHEMA_WITHOUT_PORT = {
    vol.Optional(CONF_SERVER_HOST): vol.All(
        cv.ensure_list, vol.Length(min=1), [cv.string]
    ),
    vol.Optional(CONF_SSL_CERTIFICATE): cv.isfile,
    vol.Optional(CONF_SSL_PEER_CERTIFICATE): cv.isfile,
    vol.Optional(CONF_SSL_KEY): cv.isfile,
    vol.Optional(CONF_SSL_PROFILE, default=SSL_MODERN): vol.In(
        [SSL_INTERMEDIATE, SSL_MODERN]
    ),
}

OPTIONAL_PORT = {vol.Optional(CONF_SERVER_PORT, default=SERVER_PORT): cv.port}

_EXCLUSIVE_PORT_KEY = vol.Exclusive(CONF_SERVER_PORT, "server")
_EXCLUSIVE_PORT_KEY.default = vol.default_factory(SERVER_PORT)

EXCLUSIVE_PORT = {_EXCLUSIVE_PORT_KEY: cv.port}


def _has_all_unique_ports(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate that each http service has a unique port."""
    ports = [list[CONF_SERVER_PORT] for list in servers]
    vol.Schema(vol.Unique())(ports)
    return servers


SERVERS_EXCLUSIVE_MESSAGE = (
    'Configure one server at top level or configure multiple servers under "servers"'
)


HTTP_SCHEMA: Final = vol.All(
    cv.deprecated(CONF_BASE_URL),
    cv.deprecated(CONF_SERVER_HOST),
    cv.deprecated(CONF_SERVER_PORT),
    cv.deprecated(CONF_SSL_CERTIFICATE),
    cv.deprecated(CONF_SSL_PEER_CERTIFICATE),
    cv.deprecated(CONF_SSL_KEY),
    cv.deprecated(CONF_SSL_PROFILE),
    vol.Schema(
        {
            **SERVER_SCHEMA_WITHOUT_PORT,
            **EXCLUSIVE_PORT,
            vol.Optional(CONF_BASE_URL): cv.string,
            vol.Exclusive(
                CONF_SERVERS, "servers", msg=SERVERS_EXCLUSIVE_MESSAGE
            ): vol.All(
                cv.ensure_list,
                [vol.Schema({**SERVER_SCHEMA_WITHOUT_PORT, **OPTIONAL_PORT})],
                _has_all_unique_ports,
            ),
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
    trusted_proxies: list[IPv4Network | IPv6Network]
    login_attempts_threshold: int
    ip_ban_enabled: bool
    ssl_profile: str


@bind_hass
async def async_get_last_config(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return the last known working config."""
    store = storage.Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    return await store.async_load()


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


@dataclass
class SiteServerConfig:
    """Configuration for a single TCPSite."""

    server_host: list[str] | None
    server_port: int
    ssl_certificate: str | None
    ssl_peer_certificate: str | None
    ssl_key: str | None
    ssl_profile: str
    ssl_context: ssl.SSLContext | None = None


def _create_site_server_config_from_dict(conf: ConfData) -> SiteServerConfig:
    """Create a SiteServerConfig from a dict."""
    return SiteServerConfig(
        server_host=conf.get(CONF_SERVER_HOST),
        server_port=conf[CONF_SERVER_PORT],
        ssl_certificate=conf.get(CONF_SSL_CERTIFICATE),
        ssl_peer_certificate=conf.get(CONF_SSL_PEER_CERTIFICATE),
        ssl_key=conf.get(CONF_SSL_KEY),
        ssl_profile=conf[CONF_SSL_PROFILE],
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HTTP API and debug interface."""
    conf: ConfData | None = config.get(DOMAIN)

    if conf is None:
        conf = cast(ConfData, HTTP_SCHEMA({}))

    # configuration options that affect all TCPSites
    cors_origins = conf[CONF_CORS_ORIGINS]
    use_x_forwarded_for = conf.get(CONF_USE_X_FORWARDED_FOR, False)
    trusted_proxies = conf.get(CONF_TRUSTED_PROXIES) or []
    is_ban_enabled = conf[CONF_IP_BAN_ENABLED]
    login_threshold = conf[CONF_LOGIN_ATTEMPTS_THRESHOLD]

    site_configs: list[SiteServerConfig] = []

    if server_cfg := conf.get(CONF_SERVERS):
        servers = cast(list[ConfData], server_cfg)
        site_configs = [_create_site_server_config_from_dict(cfg) for cfg in servers]
    else:
        site_configs = [_create_site_server_config_from_dict(conf)]

    server = HomeAssistantHTTP(
        hass,
        site_configs=site_configs,
        trusted_proxies=trusted_proxies,
    )
    await server.async_initialize(
        cors_origins=cors_origins,
        use_x_forwarded_for=use_x_forwarded_for,
        login_threshold=login_threshold,
        is_ban_enabled=is_ban_enabled,
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
    primary_server_conf = site_configs[0]
    local_ip = await async_get_source_ip(hass)

    if primary_server_host := primary_server_conf.server_host:
        primary_host = primary_server_host[0]
    else:
        primary_host = local_ip

    hass.config.api = ApiConfig(
        local_ip,
        primary_host,
        primary_server_conf.server_port,
        all(site_config.ssl_certificate is not None for site_config in site_configs),
    )

    return True


class HomeAssistantAccessLogger(AccessLogger):
    """Access logger for Home Assistant that does not log when disabled."""

    def log(
        self, request: web.BaseRequest, response: web.StreamResponse, time: float
    ) -> None:
        """Log the request.

        The default implementation logs the request to the logger
        with the INFO level and than throws it away if the logger
        is not enabled for the INFO level. This implementation
        does not log the request if the logger is not enabled for
        the INFO level.
        """
        if not self.logger.isEnabledFor(logging.INFO):
            return
        super().log(request, response, time)


class HomeAssistantRequest(web.Request):
    """Home Assistant request object."""

    async def json(self, *, loads: JSONDecoder = json_loads) -> Any:
        """Return body as JSON."""
        # json_loads is a wrapper around orjson.loads that handles
        # bytes and str. We can pass the bytes directly to json_loads.
        return json_loads(await self.read())


class HomeAssistantApplication(web.Application):
    """Home Assistant application."""

    def _make_request(
        self,
        message: RawRequestMessage,
        payload: StreamReader,
        protocol: RequestHandler,
        writer: AbstractStreamWriter,
        task: asyncio.Task[None],
        _cls: type[web.Request] = HomeAssistantRequest,
    ) -> web.Request:
        """Create request instance."""
        return _cls(
            message,
            payload,
            protocol,
            writer,
            task,
            loop=self._loop,
            client_max_size=self._client_max_size,
        )


class HomeAssistantHTTP:
    """HTTP server for Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        site_configs: list[SiteServerConfig],
        trusted_proxies: list[IPv4Network | IPv6Network],
    ) -> None:
        """Initialize the HTTP Home Assistant server."""
        self.app = HomeAssistantApplication(
            middlewares=[],
            client_max_size=MAX_CLIENT_SIZE,
            handler_args={
                "max_line_size": MAX_LINE_SIZE,
                "max_field_size": MAX_LINE_SIZE,
            },
        )
        self.hass = hass
        self.site_configs = site_configs
        self.trusted_proxies = trusted_proxies
        self.runner: web.AppRunner | None = None
        self.sites: list[HomeAssistantTCPSite] = []
        # For backwards compat
        self.server_port: int = site_configs[0].server_port

    async def async_initialize(
        self,
        *,
        cors_origins: list[str],
        use_x_forwarded_for: bool,
        login_threshold: int,
        is_ban_enabled: bool,
    ) -> None:
        """Initialize the server."""
        self.app[KEY_HASS] = self.hass

        # Order matters, security filters middleware needs to go first,
        # forwarded middleware needs to go second.
        setup_security_filter(self.app)

        async_setup_forwarded(self.app, use_x_forwarded_for, self.trusted_proxies)

        setup_request_context(self.app, current_request)

        if is_ban_enabled:
            setup_bans(self.hass, self.app, login_threshold)

        await async_setup_auth(self.hass, self.app)

        setup_cors(self.app, cors_origins)

        if any(site.ssl_certificate for site in self.site_configs):
            await self.hass.async_add_executor_job(self._create_ssl_contexts)

    def register_view(self, view: HomeAssistantView | type[HomeAssistantView]) -> None:
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

        self.app["allow_configured_cors"](
            self.app.router.add_route("GET", url, redirect)
        )

    def register_static_path(
        self, url_path: str, path: str, cache_headers: bool = True
    ) -> None:
        """Register a folder or file to serve as a static path."""
        if os.path.isdir(path):
            if cache_headers:
                resource: CachingStaticResource | web.StaticResource = (
                    CachingStaticResource(url_path, path)
                )
            else:
                resource = web.StaticResource(url_path, path)
            self.app.router.register_resource(resource)
            self.app["allow_configured_cors"](resource)
            return

        async def serve_file(request: web.Request) -> web.FileResponse:
            """Serve file from disk."""
            if cache_headers:
                return web.FileResponse(path, headers=CACHE_HEADERS)
            return web.FileResponse(path)

        self.app["allow_configured_cors"](
            self.app.router.add_route("GET", url_path, serve_file)
        )

    def _create_ssl_contexts(self) -> None:
        for site in self.site_configs:
            context: ssl.SSLContext | None = None
            if site.ssl_certificate is None:
                continue
            try:
                if site.ssl_profile == SSL_INTERMEDIATE:
                    context = ssl_util.server_context_intermediate()
                else:
                    context = ssl_util.server_context_modern()
                context.load_cert_chain(site.ssl_certificate, site.ssl_key)
            except OSError as error:
                if not self.hass.config.safe_mode:
                    raise HomeAssistantError(
                        f"Could not use SSL certificate from {site.ssl_certificate}:"
                        f" {error}"
                    ) from error
                _LOGGER.error(
                    "Could not read SSL certificate from %s: %s",
                    site.ssl_certificate,
                    error,
                )
                try:
                    context = self._create_emergency_ssl_context()
                except OSError as os_error:
                    _LOGGER.error(
                        "Could not create an emergency self signed ssl certificate: %s",
                        os_error,
                    )
                    continue
                else:
                    _LOGGER.critical(
                        "Home Assistant is running in safe mode with an emergency self"
                        " signed ssl certificate because the configured SSL certificate was"
                        " not usable"
                    )
                    site.ssl_context = context
                    continue

            if site.ssl_peer_certificate:
                if context is None:
                    raise HomeAssistantError(
                        "Failed to create ssl context, no fallback available because a peer"
                        " certificate is required."
                    )

                context.verify_mode = ssl.CERT_REQUIRED
                context.load_verify_locations(site.ssl_peer_certificate)

            site.ssl_context = context

    def _create_emergency_ssl_context(self) -> ssl.SSLContext:
        """Create an emergency ssl certificate so we can still startup."""
        context = ssl_util.server_context_modern()
        host: str
        try:
            host = cast(str, URL(get_url(self.hass, prefer_external=True)).host)
        except NoURLAvailableError:
            host = "homeassistant.local"
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(
                    NameOID.ORGANIZATION_NAME, "Home Assistant Emergency Certificate"
                ),
                x509.NameAttribute(NameOID.COMMON_NAME, host),
            ]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=30))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(host)]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        with NamedTemporaryFile() as cert_pem, NamedTemporaryFile() as key_pem:
            cert_pem.write(cert.public_bytes(serialization.Encoding.PEM))
            key_pem.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            cert_pem.flush()
            key_pem.flush()
            context.load_cert_chain(cert_pem.name, key_pem.name)
        return context

    async def start(self) -> None:
        """Start the aiohttp server."""
        # Aiohttp freezes apps after start so that no changes can be made.
        # However in Home Assistant components can be discovered after boot.
        # This will now raise a RunTimeError.
        # To work around this we now prevent the router from getting frozen
        # pylint: disable-next=protected-access
        self.app._router.freeze = lambda: None  # type: ignore[method-assign]

        self.runner = web.AppRunner(
            self.app, access_log_class=HomeAssistantAccessLogger
        )
        await self.runner.setup()

        sites = [
            HomeAssistantTCPSite(
                self.runner,
                site_config.server_host,
                site_config.server_port,
                ssl_context=site_config.ssl_context,
            )
            for site_config in self.site_configs
        ]

        results = await asyncio.gather(
            *(site.start() for site in sites), return_exceptions=True
        )

        for idx, result in enumerate(results):
            site_config = self.site_configs[idx]

            if isinstance(result, Exception):
                _LOGGER.error(
                    "Failed to create HTTP server at port %s:%d: %s",
                    site_config.server_host,
                    site_config.server_port,
                    result,
                )
                continue

            self.sites.append(sites[idx])
            _LOGGER.info(
                "Now listening on %s:%d",
                site_config.server_host,
                site_config.server_port,
            )

    async def stop(self) -> None:
        """Stop the aiohttp server."""
        if self.sites:
            await asyncio.gather(*(site.stop() for site in self.sites))
        if self.runner is not None:
            await self.runner.cleanup()


async def start_http_server_and_save_config(
    hass: HomeAssistant, conf: dict, server: HomeAssistantHTTP
) -> None:
    """Startup the http server and save the config."""
    await server.start()

    # If we are set up successful, we store the HTTP settings for safe mode.
    store: storage.Store[dict[str, Any]] = storage.Store(
        hass, STORAGE_VERSION, STORAGE_KEY
    )

    if CONF_TRUSTED_PROXIES in conf:
        conf[CONF_TRUSTED_PROXIES] = [
            str(cast(IPv4Network | IPv6Network, ip).network_address)
            for ip in conf[CONF_TRUSTED_PROXIES]
        ]

    store.async_delay_save(lambda: conf, SAVE_DELAY)
