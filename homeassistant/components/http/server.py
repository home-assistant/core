"""HTTP server implementation for the Home Assistant HTTP integration."""

import asyncio
from collections.abc import Collection
from dataclasses import dataclass
import datetime
from functools import partial
from ipaddress import IPv4Network, IPv6Network, ip_network
import logging
import os
from pathlib import Path
import socket
import ssl
from tempfile import NamedTemporaryFile
from typing import Any, Final, cast, override

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
from yarl import URL

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.http import (
    KEY_ALLOW_CONFIGURED_CORS,
    KEY_HASS,
    HomeAssistantView,
    current_request,
)
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util, ssl as ssl_util
from homeassistant.util.json import json_loads

from .auth import async_setup_auth
from .ban import setup_bans
from .config import ConfData
from .const import (
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    CONF_SSL_PEER_CERTIFICATE,
    CONF_SSL_PROFILE,
    CONF_TRUSTED_PROXIES,
    SSL_INTERMEDIATE,
)
from .cors import setup_cors
from .forwarded import async_setup_forwarded
from .headers import setup_headers
from .request_context import setup_request_context
from .security_filter import setup_security_filter
from .static import CACHE_HEADERS, CachingStaticResource
from .web_runner import HomeAssistantUnixSite

_LOGGER: Final = logging.getLogger(__name__)

MAX_CLIENT_SIZE: Final = 1024**2 * 16
MAX_LINE_SIZE: Final = 24570

_HAS_IPV6 = hasattr(socket, "AF_INET6")
DEFAULT_BIND = ["0.0.0.0", "::"] if _HAS_IPV6 else ["0.0.0.0"]


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


def make_server(
    hass: HomeAssistant,
    conf: ConfData,
    supervisor_unix_socket_path: Path | None = None,
) -> HomeAssistantHTTP:
    """Create a server instance for the given config."""
    return HomeAssistantHTTP(
        hass,
        server_host=conf.get(CONF_SERVER_HOST, DEFAULT_BIND),
        server_port=conf[CONF_SERVER_PORT],
        ssl_certificate=conf.get(CONF_SSL_CERTIFICATE),
        ssl_peer_certificate=conf.get(CONF_SSL_PEER_CERTIFICATE),
        ssl_key=conf.get(CONF_SSL_KEY),
        # The loaded config stores trusted proxies as strings
        # (JSON-serializable); the forwarded middleware needs
        # IPv4Network/IPv6Network objects.
        trusted_proxies=[
            ip_network(proxy) for proxy in conf.get(CONF_TRUSTED_PROXIES) or []
        ],
        ssl_profile=conf[CONF_SSL_PROFILE],
        supervisor_unix_socket_path=supervisor_unix_socket_path,
    )


async def async_verify_can_bind(hass: HomeAssistant, conf: ConfData) -> None:
    """Verify a server for ``conf`` can be created and its address bound.

    Used to validate a new user-supplied config before it is stored and
    applied via a restart; the sockets are released right away. Best effort:
    the address can still be taken by another process before the restart, so
    the setup fallback chain remains the safety net.

    Raises ``HomeAssistantError`` if the SSL configuration is unusable or the
    configured address cannot be bound.
    """
    server = make_server(hass, conf)
    try:
        await server.async_bind()
    except OSError as err:
        raise HomeAssistantError(
            f"Failed to create HTTP server at port {conf[CONF_SERVER_PORT]}: {err}"
        ) from err
    finally:
        await server.stop()


class HomeAssistantRequest(web.Request):
    """Home Assistant request object."""

    @override
    async def json(self, *, loads: JSONDecoder = json_loads) -> Any:
        """Return body as JSON."""
        # json_loads is a wrapper around orjson.loads that handles
        # bytes and str. We can pass the bytes directly to json_loads.
        return json_loads(await self.read())


class HomeAssistantApplication(web.Application):
    """Home Assistant application."""

    @override
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
            # loop will never be None when called from aiohttp
            loop=self._loop,  # type: ignore[arg-type]
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
        supervisor_unix_socket_path: Path | None = None,
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
        self.supervisor_unix_socket_path = supervisor_unix_socket_path
        self.runner: web.AppRunner | None = None
        self.supervisor_site: HomeAssistantUnixSite | None = None
        self.context: ssl.SSLContext | None = None
        self._server: asyncio.Server | None = None

    async def async_bind(self) -> None:
        """Create the SSL context and the server, binding its sockets.

        Called during setup so that an unusable configuration surfaces before
        it is applied; serving starts later in ``start()``. Raises
        ``HomeAssistantError`` if the SSL configuration is unusable and
        ``OSError`` if the configured address cannot be bound.
        """
        if self.ssl_certificate:
            self.context = await self.hass.async_add_executor_job(
                self._create_ssl_context
            )
        self._server = await self._async_create_server()

    async def _async_create_server(self) -> asyncio.Server:
        """Create the (not yet serving) HTTP server, binding its sockets."""
        try:
            return await self.hass.loop.create_server(
                self._make_protocol,
                self.server_host if self.server_host is not None else DEFAULT_BIND,
                self.server_port,
                ssl=self.context,
                backlog=128,
                start_serving=False,
            )
        except UnicodeError as err:
            # create_server() raises UnicodeError for hosts the IDNA codec
            # cannot encode (e.g. a label longer than 63 characters);
            # normalize to OSError so callers only need to handle one error
            # type.
            raise OSError(f"error while resolving host: {err}") from err

    def _make_protocol(self) -> RequestHandler:
        """Create a protocol instance for an accepted connection.

        Connections are only accepted once ``start()`` has run, so the
        runner is set up by the time this is called.
        """
        runner = self.runner
        assert runner is not None and runner.server is not None
        return runner.server()

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
            raise redirect_exc(redirect_to)  # type: ignore[arg-type,call-arg]

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
                # Fall through: a configured peer certificate must still be
                # enforced on the emergency context.
                _LOGGER.critical(
                    "Home Assistant is running in recovery mode with an emergency self"
                    " signed ssl certificate because the configured SSL certificate was"
                    " not usable"
                )

        if self.ssl_peer_certificate:
            if context is None:
                raise HomeAssistantError(
                    "Failed to create ssl context, no fallback available because a peer"
                    " certificate is required."
                )

            context.verify_mode = ssl.CERT_REQUIRED
            try:
                context.load_verify_locations(self.ssl_peer_certificate)
            except OSError as error:
                # Raise HomeAssistantError so the caller can tell an unusable
                # SSL configuration apart from a socket bind failure (OSError).
                raise HomeAssistantError(
                    f"Could not use SSL peer certificate from"
                    f" {self.ssl_peer_certificate}: {error}"
                ) from error

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

    async def async_start_supervisor_unix_socket(self) -> None:
        """Start listening on the Unix socket.

        This is called separately from start() to delay serving the Unix
        socket until the Supervisor user exists (created by the hassio
        integration).  Without this delay, Supervisor could connect before
        its user is available and receive 401 responses it won't retry.
        """
        if self.supervisor_unix_socket_path is None or self.runner is None:
            return
        self.supervisor_site = HomeAssistantUnixSite(
            self.runner, self.supervisor_unix_socket_path
        )
        try:
            await self.supervisor_site.start()
        except OSError as error:
            _LOGGER.error(
                "Failed to create HTTP server on unix socket %s: %s",
                self.supervisor_unix_socket_path,
                error,
            )
            self.supervisor_site = None
        else:
            _LOGGER.info(
                "Now listening on unix socket %s", self.supervisor_unix_socket_path
            )

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

        # Setup either binds the server or fails, so it is always available
        # here.
        assert self._server is not None
        await self._server.start_serving()

        _LOGGER.info("Now listening on port %d", self.server_port)

    async def stop(self) -> None:
        """Stop the aiohttp server."""
        if self.supervisor_site is not None:
            await self.supervisor_site.stop()
            if self.supervisor_unix_socket_path is not None:
                try:
                    await self.hass.async_add_executor_job(
                        self.supervisor_unix_socket_path.unlink, True
                    )
                except OSError as err:
                    _LOGGER.warning(
                        "Could not remove Supervisor unix socket %s: %s",
                        self.supervisor_unix_socket_path,
                        err,
                    )
        if self._server is not None:
            # Only close (stop listening); do not await wait_closed() here.
            # Let runner.cleanup() terminate active connections.
            self._server.close()
        if self.runner is not None:
            await self.runner.cleanup()
