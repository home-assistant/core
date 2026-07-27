"""Support to serve the Home Assistant API as WSGI application."""

from ipaddress import ip_network
import logging
import os
from pathlib import Path
from typing import Any, Final

import voluptuous as vol

from homeassistant.components.network import async_get_source_ip
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    HASSIO_USER_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.http import (  # noqa: F401
    KEY_ALLOW_CONFIGURED_CORS,
    KEY_AUTHENTICATED,
    KEY_HASS,
    HomeAssistantView,
    current_request,
)
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import (
    SetupPhases,
    async_start_setup,
    async_when_setup_or_start,
)
from homeassistant.util.async_ import create_eager_task

from .config import async_get_and_load_store, async_load_config, default_server_port
from .const import (  # noqa: F401
    CONF_BASE_URL,
    CONF_CORS_ORIGINS,
    CONF_IP_BAN_ENABLED,
    CONF_LOGIN_ATTEMPTS_THRESHOLD,
    CONF_SERVER_HOST,
    CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    CONF_SSL_PEER_CERTIFICATE,
    CONF_SSL_PROFILE,
    CONF_TRUSTED_PROXIES,
    CONF_USE_X_FORWARDED_FOR,
    CONF_USE_X_FRAME_OPTIONS,
    DEFAULT_CORS,
    DOMAIN,
    KEY_HASS_REFRESH_TOKEN_ID,
    KEY_HASS_USER,
    NO_LOGIN_ATTEMPT_THRESHOLD,
    SSL_INTERMEDIATE,
    SSL_MODERN,
)
from .decorators import require_admin  # noqa: F401
from .server import (
    DEFAULT_BIND,
    HomeAssistantHTTP,  # noqa: F401
    HomeAssistantRequest,  # noqa: F401
    StaticPathConfig,  # noqa: F401
    make_server,
)

_LOGGER: Final = logging.getLogger(__name__)

DEFAULT_DEVELOPMENT: Final = "0"

HTTP_SCHEMA: Final = vol.All(
    cv.deprecated(CONF_BASE_URL),
    vol.Schema(
        {
            vol.Optional(CONF_SERVER_HOST): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
            vol.Optional(CONF_SERVER_PORT, default=default_server_port): cv.port,
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

    # Deferred import: websocket_api declares http as its manifest
    # dependency and imports back into this package at module load
    # (websocket_api/http.py -> homeassistant.components.http). A top-level
    # import of .websocket_api here would re-enter the still-loading
    # websocket_api package and fail when applying its decorators
    # (e.g. @websocket_api.require_admin).
    websocket_api_module = await async_import_module(
        hass, "homeassistant.components.http.websocket_api"
    )

    conf = await async_load_config(hass, config)

    websocket_api_module.async_register_websocket_commands(hass)

    supervisor_unix_socket_path: Path | None = None
    if socket_env := os.environ.get("SUPERVISOR_CORE_API_SOCKET"):
        socket_path = Path(socket_env)
        if socket_path.is_absolute():
            supervisor_unix_socket_path = socket_path
        else:
            _LOGGER.error(
                "Invalid Supervisor Unix socket path %s: path must be absolute",
                socket_env,
            )

    server = make_server(hass, conf, supervisor_unix_socket_path)
    trial_reverted = False
    while True:
        try:
            await server.async_bind()
        except (HomeAssistantError, OSError) as err:
            store = await async_get_and_load_store(hass)
            trial_reverted = store.revert_deadline is not None
            conf = await store.async_get_fallback_config(err)
            server = make_server(hass, conf, supervisor_unix_socket_path)
            continue
        if trial_reverted:
            _LOGGER.warning(
                "The previous HTTP configuration has been restored (server port %d)",
                conf[CONF_SERVER_PORT],
            )
        break

    # Created only after the fallback chain succeeded: if setup fails above,
    # an already running task would be left behind unawaited.
    source_ip_task = create_eager_task(async_get_source_ip(hass))

    async def stop_server(event: Event) -> None:
        """Stop the server."""
        await server.stop()

    # Register the stop listener right away, not only once serving starts:
    # sockets are already bound, and if the remainder of startup fails the
    # recovery-mode teardown (which fires the stop event) must release them,
    # or the recovery boot cannot bind the same address again.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_server)

    if CONF_SERVER_HOST in conf and is_hassio(hass):
        issue_id = "server_host_deprecated_hassio"
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2026.6.0",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=issue_id,
        )

    server_host = conf.get(CONF_SERVER_HOST, DEFAULT_BIND)
    server_port = conf[CONF_SERVER_PORT]
    ssl_certificate = conf.get(CONF_SSL_CERTIFICATE)

    await server.async_initialize(
        cors_origins=conf[CONF_CORS_ORIGINS],
        use_x_forwarded_for=conf.get(CONF_USE_X_FORWARDED_FOR, False),
        login_threshold=conf[CONF_LOGIN_ATTEMPTS_THRESHOLD],
        is_ban_enabled=conf[CONF_IP_BAN_ENABLED],
        use_x_frame_options=conf[CONF_USE_X_FRAME_OPTIONS],
    )

    async def start_server(*_: Any) -> None:
        """Start the server."""
        with async_start_setup(hass, integration="http", phase=SetupPhases.SETUP):
            await server.start()

    async_when_setup_or_start(hass, "frontend", start_server)

    if server.supervisor_unix_socket_path is not None:

        async def start_supervisor_unix_socket(*_: Any) -> None:
            """Start the Unix socket after the Supervisor user is available."""
            if any(
                user
                for user in await hass.auth.async_get_users()
                if user.system_generated and user.name == HASSIO_USER_NAME
            ):
                await server.async_start_supervisor_unix_socket()
            else:
                _LOGGER.error("Supervisor user not found; not starting Unix socket")

        async_when_setup_or_start(hass, "hassio", start_supervisor_unix_socket)

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
            from homeassistant.components.cloud import (  # noqa: PLC0415
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
