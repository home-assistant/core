"""Ban logic for HTTP component."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import suppress
from datetime import datetime
from http import HTTPStatus
from ipaddress import IPv4Address, IPv6Address, ip_address
import logging
import os
from socket import gethostbyaddr
from typing import Any, Concatenate, Final, TypedDict

from aiohttp.web import (
    AppKey,
    Application,
    Request,
    Response,
    StreamResponse,
    middleware,
)
from aiohttp.web_exceptions import HTTPForbidden, HTTPUnauthorized
import probatio

from homeassistant.config import load_yaml_config_file
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.hassio import get_supervisor_ip, is_hassio
from homeassistant.helpers.http import KEY_HASS, HomeAssistantView
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_IP_ADDRESS,
    ATTR_IP_BANS,
    DOMAIN,
    NO_LOGIN_ATTEMPT_THRESHOLD,
    is_supervisor_unix_socket_request,
)

_LOGGER: Final = logging.getLogger(__name__)

KEY_BAN_MANAGER = AppKey["IpBanManager"]("ha_banned_ips_manager")
KEY_FAILED_LOGIN_ATTEMPTS = AppKey[defaultdict[IPv4Address | IPv6Address, int]](
    "ha_failed_login_attempts"
)
KEY_LOGIN_THRESHOLD = AppKey[int]("ban_manager.ip_bans_lookup")

NOTIFICATION_ID_BAN: Final = "ip-ban"
NOTIFICATION_ID_LOGIN: Final = "http-login"

# Imported once into the store, then renamed with MIGRATED_SUFFIX
IP_BANS_FILE: Final = "ip_bans.yaml"
MIGRATED_SUFFIX: Final = ".migrated"
STORAGE_KEY: Final = f"{DOMAIN}.ip_bans"
STORAGE_VERSION: Final = 1
ISSUE_IP_BANS_YAML_IMPORT_ERROR: Final = "ip_bans_yaml_import_error"
ISSUE_IP_BANS_YAML_IGNORED: Final = "ip_bans_yaml_ignored"
# Bound the reverse DNS lookup so a slow resolver cannot stall the response
REVERSE_DNS_TIMEOUT: Final = 1
ATTR_BANNED_AT: Final = "banned_at"
ATTR_YAML_MIGRATION_DONE: Final = "yaml_migration_done"

SCHEMA_IP_BAN_ENTRY: Final = probatio.Schema(
    {probatio.Optional(ATTR_BANNED_AT, default=None): probatio.Any(None, cv.datetime)}
)
SCHEMA_STORED_IP_BAN: Final = probatio.Schema(
    {
        probatio.Required(ATTR_IP_ADDRESS): str,
        probatio.Required(ATTR_BANNED_AT): cv.datetime,
    }
)
SCHEMA_STORE: Final = probatio.Schema(
    {
        probatio.Optional(ATTR_IP_BANS, default=list): list,
        probatio.Optional(ATTR_YAML_MIGRATION_DONE, default=False): bool,
    },
    extra=probatio.ALLOW_EXTRA,
)


class StoredIpBan(TypedDict):
    """A ban as stored and returned by the WebSocket API."""

    ip_address: str
    banned_at: str


class IpBanStoreData(TypedDict):
    """Stored IP bans."""

    ip_bans: list[StoredIpBan]
    yaml_migration_done: bool


@callback
def setup_bans(
    hass: HomeAssistant,
    app: Application,
    login_threshold: int,
    is_ban_enabled: bool = True,
) -> None:
    """Set up the IP ban manager, and the middleware when banning is enabled.

    The manager is always set up so existing bans can be listed and removed.
    """
    if is_ban_enabled:
        app.middlewares.append(ban_middleware)
    failed_login_attempts = app[KEY_FAILED_LOGIN_ATTEMPTS] = defaultdict[
        IPv4Address | IPv6Address, int
    ](int)
    app[KEY_LOGIN_THRESHOLD] = (
        login_threshold if is_ban_enabled else NO_LOGIN_ATTEMPT_THRESHOLD
    )
    app[KEY_BAN_MANAGER] = IpBanManager(hass, failed_login_attempts)

    async def ban_startup(app: Application) -> None:
        """Initialize bans when app starts up."""
        await app[KEY_BAN_MANAGER].async_load()

    app.on_startup.append(ban_startup)


@middleware
async def ban_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """IP Ban middleware."""
    # Unix socket connections are trusted, skip ban checks
    if is_supervisor_unix_socket_request(request):
        return await handler(request)

    if (ban_manager := request.app.get(KEY_BAN_MANAGER)) is None:
        _LOGGER.error("IP Ban middleware loaded but banned IPs not loaded")
        return await handler(request)

    if ip_bans_lookup := ban_manager.ip_bans_lookup:
        # Verify if IP is not banned
        ip_address_ = ip_address(request.remote)  # type: ignore[arg-type]
        if ip_address_ in ip_bans_lookup:
            raise HTTPForbidden

    try:
        return await handler(request)
    except HTTPUnauthorized:
        await process_wrong_login(request)
        raise


def log_invalid_auth[_HassViewT: HomeAssistantView, **_P](
    func: Callable[Concatenate[_HassViewT, Request, _P], Awaitable[Response]],
) -> Callable[Concatenate[_HassViewT, Request, _P], Coroutine[Any, Any, Response]]:
    """Decorate function to handle invalid auth or failed login attempts."""

    async def handle_req(
        view: _HassViewT, request: Request, *args: _P.args, **kwargs: _P.kwargs
    ) -> Response:
        """Try to log failed login attempts if response status >= BAD_REQUEST."""
        resp = await func(view, request, *args, **kwargs)
        if resp.status >= HTTPStatus.BAD_REQUEST:
            await process_wrong_login(request)
        return resp

    return handle_req


async def process_wrong_login(request: Request) -> None:
    """Process a wrong login attempt.

    Increase failed login attempts counter for remote IP address.
    Add ip ban entry if failed login attempts exceeds threshold.
    """
    hass = request.app[KEY_HASS]

    assert request.remote
    remote_addr = ip_address(request.remote)
    # Before the reverse DNS lookup, so a ban already applies to the next request.
    banned = await _async_count_wrong_login(request.app, hass, remote_addr)

    remote_host = request.remote
    # The hostname only feeds the log and notification below
    with suppress(TimeoutError, OSError, UnicodeError):
        async with asyncio.timeout(REVERSE_DNS_TIMEOUT):
            remote_host, _, _ = await hass.async_add_executor_job(
                gethostbyaddr, request.remote
            )

    base_msg = (
        "Login attempt or request with invalid authentication from"
        f" {remote_host} ({remote_addr})."
    )

    # The user-agent is unsanitized input so we only include it in the log
    user_agent = request.headers.get("user-agent")
    log_msg = f"{base_msg} Requested URL: '{request.rel_url}'. ({user_agent})"

    notification_msg = f"{base_msg} See the log for details."

    _LOGGER.warning(log_msg)

    # Circular import with websocket_api
    from homeassistant.components import persistent_notification  # noqa: PLC0415

    persistent_notification.async_create(
        hass, notification_msg, "Login attempt failed", NOTIFICATION_ID_LOGIN
    )

    if banned:
        _LOGGER.warning("Banned IP %s for too many login attempts", remote_addr)
        persistent_notification.async_create(
            hass,
            f"Too many login attempts from {remote_addr}. You can unblock it under"
            " [Settings > System > Network](/config/network).",
            "Banning IP address",
            NOTIFICATION_ID_BAN,
        )


async def _async_count_wrong_login(
    app: Application, hass: HomeAssistant, remote_addr: IPv4Address | IPv6Address
) -> bool:
    """Count a wrong login attempt and return if it got the address banned."""
    # Check if ban middleware is loaded
    if KEY_BAN_MANAGER not in app or app[KEY_LOGIN_THRESHOLD] < 1:
        return False

    app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] += 1

    # Supervisor IP should never be banned
    if is_hassio(hass) and str(remote_addr) == get_supervisor_ip():
        return False

    if app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] < app[KEY_LOGIN_THRESHOLD]:
        return False

    await app[KEY_BAN_MANAGER].async_add_ban(remote_addr)
    return True


@callback
def process_success_login(request: Request) -> None:
    """Process a success login attempt.

    Reset failed login attempts counter for remote IP address.
    """
    app = request.app
    # Check if ban middleware is loaded
    if KEY_BAN_MANAGER not in app or app[KEY_LOGIN_THRESHOLD] < 1:
        return

    remote_addr = ip_address(request.remote)  # type: ignore[arg-type]
    login_attempt_history = app[KEY_FAILED_LOGIN_ATTEMPTS]
    if remote_addr in login_attempt_history and login_attempt_history[remote_addr] > 0:
        _LOGGER.debug(
            "Login success, reset failed login attempts counter from %s", remote_addr
        )
        login_attempt_history.pop(remote_addr)


class IpBan:
    """Represents banned IP address."""

    def __init__(
        self,
        ip_ban: str | IPv4Address | IPv6Address,
        banned_at: datetime | None = None,
    ) -> None:
        """Initialize IP Ban object."""
        self.ip_address = ip_address(ip_ban)
        if banned_at is None:
            banned_at = dt_util.utcnow()
        elif banned_at.tzinfo is None:
            # Old versions wrote naive UTC timestamps to ip_bans.yaml
            banned_at = banned_at.replace(tzinfo=dt_util.UTC)
        self.banned_at = dt_util.as_utc(banned_at)

    def as_dict(self) -> StoredIpBan:
        """Return the ban as stored and returned by the WebSocket API."""
        return {
            ATTR_IP_ADDRESS: str(self.ip_address),
            ATTR_BANNED_AT: self.banned_at.isoformat(),
        }


class IpBanManager:
    """Manage IP bans."""

    def __init__(
        self,
        hass: HomeAssistant,
        failed_login_attempts: defaultdict[IPv4Address | IPv6Address, int],
    ) -> None:
        """Init the ban manager."""
        self.hass = hass
        self.ip_bans_lookup: dict[IPv4Address | IPv6Address, IpBan] = {}
        self._failed_login_attempts = failed_login_attempts
        self._store = Store[IpBanStoreData](
            hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self._yaml_migration_done = False

    async def async_load(self) -> None:
        """Load the IP bans, importing ip_bans.yaml once.

        A missing or unreadable store means no bans, so it can never keep
        the HTTP server from starting.
        """
        try:
            data = await self._store.async_load()
        except HomeAssistantError as err:
            _LOGGER.error("Unable to load the IP bans: %s", err)
            data = None
        if data is not None:
            try:
                data = SCHEMA_STORE(data)
            except probatio.Invalid as err:
                _LOGGER.error("Unable to load the IP bans: %s", err)
                data = None
        if data is not None:
            self._yaml_migration_done = data[ATTR_YAML_MIGRATION_DONE]
            for entry in data[ATTR_IP_BANS]:
                try:
                    entry = SCHEMA_STORED_IP_BAN(entry)
                    ban = IpBan(entry[ATTR_IP_ADDRESS], entry[ATTR_BANNED_AT])
                except probatio.Invalid, ValueError:
                    _LOGGER.error("Failed to load IP ban %s", entry)
                    continue
                self.ip_bans_lookup[ban.ip_address] = ban

        path = self.hass.config.path(IP_BANS_FILE)
        if not self._yaml_migration_done:
            await self._async_import_yaml(path)
        elif await self.hass.async_add_executor_job(os.path.isfile, path):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_IP_BANS_YAML_IGNORED,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_IP_BANS_YAML_IGNORED,
            )

    async def _async_import_yaml(self, path: str) -> None:
        """Import ip_bans.yaml into the store and rename it."""
        try:
            list_ = await self.hass.async_add_executor_job(load_yaml_config_file, path)
        except FileNotFoundError:
            list_ = None
        except HomeAssistantError as err:
            # Not marked as migrated, so the file is imported once it is fixed
            _LOGGER.error("Unable to load %s: %s", path, err)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_IP_BANS_YAML_IMPORT_ERROR,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_IP_BANS_YAML_IMPORT_ERROR,
            )
            return

        for ip_ban, ip_info in (list_ or {}).items():
            try:
                ip_info = SCHEMA_IP_BAN_ENTRY(ip_info)
                ban = IpBan(ip_ban, ip_info["banned_at"])
            except probatio.Invalid as err:
                _LOGGER.error("Failed to load IP ban %s: %s", ip_info, err)
                continue
            except ValueError:
                _LOGGER.error("Failed to load IP ban: invalid IP address %s", ip_ban)
                continue
            self.ip_bans_lookup.setdefault(ban.ip_address, ban)

        self._yaml_migration_done = True
        await self._async_save()
        if list_ is None:
            return

        # Store errors are only logged; keep the file unless the import is stored
        stored = await self._store.async_load()
        if stored is None or not stored.get(ATTR_YAML_MIGRATION_DONE):
            _LOGGER.error("Unable to store the IP bans imported from %s", path)
            return
        migrated_path = f"{path}{MIGRATED_SUFFIX}"
        try:
            await self.hass.async_add_executor_job(os.replace, path, migrated_path)
        except OSError as err:
            _LOGGER.error("Unable to rename %s: %s", path, err)
            return
        _LOGGER.info(
            "Imported the IP bans from %s and renamed it to %s", path, migrated_path
        )

    async def _async_save(self) -> None:
        """Save the IP bans."""
        await self._store.async_save(
            {
                ATTR_IP_BANS: [ban.as_dict() for ban in self.ip_bans_lookup.values()],
                ATTR_YAML_MIGRATION_DONE: self._yaml_migration_done,
            }
        )

    async def async_add_ban(self, remote_addr: IPv4Address | IPv6Address) -> None:
        """Add a new IP address to the banned list."""
        if remote_addr not in self.ip_bans_lookup:
            # Applies right away; a failed save is logged by the store
            self.ip_bans_lookup[remote_addr] = IpBan(remote_addr)
            await self._async_save()

    async def async_remove_ban(self, remote_addr: IPv4Address | IPv6Address) -> bool:
        """Lift a ban and reset the failed login attempts of the address.

        Return False when the address is not banned.
        """
        if self.ip_bans_lookup.pop(remote_addr, None) is None:
            return False
        self._failed_login_attempts.pop(remote_addr, None)
        await self._async_save()
        return True
