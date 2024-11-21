"""Support to serve the Home Assistant API as WSGI application."""

from __future__ import annotations

import asyncio
from collections.abc import Collection
from dataclasses import dataclass
import datetime
from functools import partial
from ipaddress import IPv4Network, IPv6Network, ip_network
import logging
import os
import socket
import ssl
from tempfile import NamedTemporaryFile
from typing import Any, Final, TypedDict, cast

from aiohttp import web
from aiohttp.abc import AbstractStreamWriter
from aiohttp.http_parser import RawRequestMessage
from aiohttp.streams import StreamReader
from aiohttp.typedefs import JSONDecoder, StrOrURL
from aiohttp.web_exceptions import HTTPMovedPermanently, HTTPRedirection
from aiohttp.web_protocol import RequestHandler
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import voluptuous as vol
from yarl import URL

from homeassistant.components.network import async_get_source_ip
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    SERVER_PORT,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import frame, issue_registry as ir, storage
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.http import (
    KEY_ALLOW_CONFIGURED_CORS,
    KEY_AUTHENTICATED,  # noqa: F401
    KEY_HASS,
    HomeAssistantView,
    current_request,
)
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.setup import (
    SetupPhases,
    async_start_setup,
    async_when_setup_or_start,
)
from homeassistant.util import dt as dt_util, ssl as ssl_util
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.json import json_loads

from .auth import async_setup_auth
from .ban import setup_bans
from .const import DOMAIN, KEY_HASS_REFRESH_TOKEN_ID, KEY_HASS_USER  # noqa: F401
from .cors import setup_cors
from .decorators import require_admin  # noqa: F401
from .forwarded import async_setup_forwarded
from .headers import setup_headers
from .request_context import setup_request_context
from .security_filter import setup_security_filter
from .static import CACHE_HEADERS, CachingStaticResource
from .web_runner import HomeAssistantTCPSite

CONF_SERVER_HOST: Final = "server_host"
CONF_SERVER_PORT: Final = "server_port"
CONF_BASE_URL: Final = "base_url"
CONF_SSL_CERTIFICATE: Final = "ssl_certificate"
CONF_SSL_PEER_CERTIFICATE: Final = "ssl_peer_certificate"
CONF_SSL_KEY: Final = "ssl_key"
CONF_CORS_ORIGINS: Final = "cors_allowed_origins"
CONF_USE_X_FORWARDED_FOR: Final = "use_x_forwarded_for"
CONF_USE_X_FRAME_OPTIONS: Final = "use_x_frame_options"
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

_HAS_IPV6 = hasattr(socket, "AF_INET6")
_DEFAULT_BIND = ["0.0.0.0", "::"] if _HAS_IPV6 else ["0.0.0.0"]

HTTP_SCHEMA: Final = vol.All(
    cv.deprecated(CONF_BASE_URL),
    vol.Schema(
        {
            vol.Optional(CONF_SERVER_HOST, default=_DEFAULT_BIND): vol.All(
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
            vol.Optional(CONF_USE_X_FRAME_OPTIONS, default=True): cv.boolean,
        }
    ),
)

CONFIG_SCHEMA: Final = vol.Schema({DOMAIN: HTTP_SCHEMA}, extra=vol.ALLOW_EXTRA)


@dataclass(slots=True)
class StaticPathConfig:
    """Configuration for a static path."""

    url_path: str
    path: str
    cache_headers: bool = True


_STATIC_CLASSES = {
    True: CachingStaticResource,
    False: web.StaticResource,
}


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
    use_x_frame_options: bool
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HTTP API and debug interface."""
    # Late import to ensure isal is updated before
    # we import aiohttp_fast_zlib
    (await async_import_module(hass, "aiohttp_fast_zlib")).enable()

    conf: ConfData | None = config.get(DOMAIN)

    if conf is None:
        conf = cast(ConfData, HTTP_SCHEMA({}))

    server_host = conf[CONF_SERVER_HOST]
    server_port = conf[CONF_SERVER_PORT]
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)
    ssl_peer_certificate = conf.get(CONF_SSL_PEER_CERTIFICATE)
    ssl_key = conf.get(CONF_SSL_KEY)
    cors_origins = conf[CONF_CORS_ORIGINS]
    use_x_forwarded_for = conf.get(CONF_USE_X_FORWARDED_FOR, False)
    use_x_frame_options = conf[CONF_USE_X_FRAME_OPTIONS]
    trusted_proxies = conf.get(CONF_TRUSTED_PROXIES) or []
    is_ban_enabled = conf[CONF_IP_BAN_ENABLED]
    login_threshold = conf[CONF_LOGIN_ATTEMPTS_THRESHOLD]
    ssl_profile = conf[CONF_SSL_PROFILE]

    source_ip_task = create_eager_task(async_get_source_ip(hass))

    server = HomeAssistantHTTP(
        hass,
        server_host=server_host,
        server_port=server_port,
        ssl_certificate=ssl_certificate,
        ssl_peer_certificate=ssl_peer_certificate,
        ssl_key=ssl_key,
        trusted_proxies=trusted_proxies,
        ssl_profile=ssl_profile,
    )
    await server.async_initialize(
        cors_origins=cors_origins,
        use_x_forwarded_for=use_x_forwarded_for,
        login_threshold=login_threshold,
        is_ban_enabled=is_ban_enabled,
        use_x_frame_options=use_x_frame_options,
    )

    async def stop_server(event: Event) -> None:
        """Stop the server."""
        await server.stop()

    async def start_server(*_: Any) -> None:
        """Start the server."""
        with async_start_setup(hass, integration="http", phase=SetupPhases.SETUP):
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_server)
            # We already checked it's not None.
            assert conf is not None
            await start_http_server_and_save_config(hass, dict(conf), server)

    async_when_setup_or_start(hass, "frontend", start_server)

    hass.http = server

    local_ip = await source_ip_task

    host = local_ip
    if server_host is not None:
        # Assume the first server host name provided as API host
        host = server_host[0]

    hass.config.api = ApiConfig(
        local_ip, host, server_port, ssl_certificate is not None
    )

    @callback
    def _async_check_ssl_issue(_: Event) -> None:
        if (
            ssl_certificate is not None
            and (hass.config.external_url or hass.config.internal_url) is None
        ):
            # pylint: disable-next=import-outside-toplevel
            from homeassistant.components.cloud import (
                CloudNotAvailable,
                async_remote_ui_url,
            )

            try:
                async_remote_ui_url(hass)
            except CloudNotAvailable:
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "ssl_configured_without_configured_urls",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="ssl_configured_without_configured_urls",
                )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_check_ssl_issue)

    return True


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


async def _serve_file_with_cache_headers(
    path: str, request: web.Request
) -> web.FileResponse:
    return web.FileResponse(path, headers=CACHE_HEADERS)


async def _serve_file(path: str, request: web.Request) -> web.FileResponse:
    return web.FileResponse(path)


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
        trusted_proxies: list[IPv4Network | IPv6Network],
        ssl_profile: str,
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
        self.ssl_certificate = ssl_certificate
        self.ssl_peer_certificate = ssl_peer_certificate
        self.ssl_key = ssl_key
        self.server_host = server_host
        self.server_port = server_port
        self.trusted_proxies = trusted_proxies
        self.ssl_profile = ssl_profile
        self.runner: web.AppRunner | None = None
        self.site: HomeAssistantTCPSite | None = None
        self.context: ssl.SSLContext | None = None

    async def async_initialize(
        self,
        *,
        cors_origins: list[str],
        use_x_forwarded_for: bool,
        login_threshold: int,
        is_ban_enabled: bool,
        use_x_frame_options: bool,
    ) -> None:
        """Initialize the server."""
        self.app[KEY_HASS] = self.hass
        self.app["hass"] = self.hass  # For backwards compatibility

        # Order matters, security filters middleware needs to go first,
        # forwarded middleware needs to go second.
        setup_security_filter(self.app)

        async_setup_forwarded(self.app, use_x_forwarded_for, self.trusted_proxies)

        setup_request_context(self.app, current_request)

        if is_ban_enabled:
            setup_bans(self.hass, self.app, login_threshold)

        await async_setup_auth(self.hass, self.app)

        setup_headers(self.app, use_x_frame_options)
        setup_cors(self.app, cors_origins)

        if self.ssl_certificate:
            self.context = await self.hass.async_add_executor_job(
                self._create_ssl_context
            )

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

        view.register(self.hass, self.app, self.app.router)

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

        self.app[KEY_ALLOW_CONFIGURED_CORS](
            self.app.router.add_route("GET", url, redirect)
        )

    def _make_static_resources(
        self, configs: Collection[StaticPathConfig]
    ) -> dict[str, CachingStaticResource | web.StaticResource | None]:
        """Create a list of static resources."""
        return {
            config.url_path: _STATIC_CLASSES[config.cache_headers](
                config.url_path, config.path
            )
            if os.path.isdir(config.path)
            else None
            for config in configs
        }

    async def async_register_static_paths(
        self, configs: Collection[StaticPathConfig]
    ) -> None:
        """Register a folder or file to serve as a static path."""
        resources = await self.hass.async_add_executor_job(
            self._make_static_resources, configs
        )
        self._async_register_static_paths(configs, resources)

    @callback
    def _async_register_static_paths(
        self,
        configs: Collection[StaticPathConfig],
        resources: dict[str, CachingStaticResource | web.StaticResource | None],
    ) -> None:
        """Register a folders or files to serve as a static path."""
        app = self.app
        allow_cors = app[KEY_ALLOW_CONFIGURED_CORS]
        for config in configs:
            if resource := resources[config.url_path]:
                app.router.register_resource(resource)
                allow_cors(resource)

            target = (
                _serve_file_with_cache_headers if config.cache_headers else _serve_file
            )
            allow_cors(
                self.app.router.add_route(
                    "GET", config.url_path, partial(target, config.path)
                )
            )

    def register_static_path(
        self, url_path: str, path: str, cache_headers: bool = True
    ) -> None:
        """Register a folder or file to serve as a static path."""
        frame.report_usage(
            "calls hass.http.register_static_path which is deprecated because "
            "it does blocking I/O in the event loop, instead "
            "call `await hass.http.async_register_static_paths("
            f'[StaticPathConfig("{url_path}", "{path}", {cache_headers})])`',
            exclude_integrations={"http"},
            core_behavior=frame.ReportBehavior.LOG,
            breaks_in_ha_version="2025.7",
        )
        configs = [StaticPathConfig(url_path, path, cache_headers)]
        resources = self._make_static_resources(configs)
        self._async_register_static_paths(configs, resources)

    def _create_ssl_context(self) -> ssl.SSLContext | None:
        context: ssl.SSLContext | None = None
        assert self.ssl_certificate is not None
        try:
            if self.ssl_profile == SSL_INTERMEDIATE:
                context = ssl_util.server_context_intermediate()
            else:
                context = ssl_util.server_context_modern()
            context.load_cert_chain(self.ssl_certificate, self.ssl_key)
        except OSError as error:
            if not self.hass.config.recovery_mode:
                raise HomeAssistantError(
                    f"Could not use SSL certificate from {self.ssl_certificate}:"
                    f" {error}"
                ) from error
            _LOGGER.error(
                "Could not read SSL certificate from %s: %s",
                self.ssl_certificate,
                error,
            )
            try:
                context = self._create_emergency_ssl_context()
            except OSError as error2:
                _LOGGER.error(
                    "Could not create an emergency self signed ssl certificate: %s",
                    error2,
                )
                context = None
            else:
                _LOGGER.critical(
                    "Home Assistant is running in recovery mode with an emergency self"
                    " signed ssl certificate because the configured SSL certificate was"
                    " not usable"
                )
                return context

        if self.ssl_peer_certificate:
            if context is None:
                raise HomeAssistantError(
                    "Failed to create ssl context, no fallback available because a peer"
                    " certificate is required."
                )

            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(self.ssl_peer_certificate)

        return context

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
        now = dt_util.utcnow()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=30))
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
        self.app._router.freeze = lambda: None  # type: ignore[method-assign]  # noqa: SLF001

        self.runner = web.AppRunner(
            self.app, handler_cancellation=True, shutdown_timeout=10
        )
        await self.runner.setup()

        self.site = HomeAssistantTCPSite(
            self.runner, self.server_host, self.server_port, ssl_context=self.context
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

    # If we are set up successful, we store the HTTP settings for recovery mode.
    store: storage.Store[dict[str, Any]] = storage.Store(
        hass, STORAGE_VERSION, STORAGE_KEY
    )

    if CONF_TRUSTED_PROXIES in conf:
        conf[CONF_TRUSTED_PROXIES] = [
            str(cast(IPv4Network | IPv6Network, ip).network_address)
            for ip in conf[CONF_TRUSTED_PROXIES]
        ]

    store.async_delay_save(lambda: conf, SAVE_DELAY)
