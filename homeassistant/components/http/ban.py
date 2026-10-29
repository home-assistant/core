"""Ban logic for HTTP component."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from http import HTTPStatus
from ipaddress import IPv4Address, IPv6Address, ip_address
import logging
from socket import gethostbyaddr
from typing import Any, Concatenate, Final

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
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.hassio import get_supervisor_ip, is_hassio
from homeassistant.helpers.http import KEY_HASS, HomeAssistantView
from homeassistant.util import dt as dt_util, yaml as yaml_util

from .const import is_supervisor_unix_socket_request

_LOGGER: Final = logging.getLogger(__name__)

KEY_BAN_MANAGER = AppKey["IpBanManager"]("ha_banned_ips_manager")
KEY_FAILED_LOGIN_ATTEMPTS = AppKey[defaultdict[IPv4Address | IPv6Address, int]](
    "ha_failed_login_attempts"
)
KEY_LOGIN_THRESHOLD = AppKey[int]("ban_manager.ip_bans_lookup")

NOTIFICATION_ID_BAN: Final = "ip-ban"
NOTIFICATION_ID_LOGIN: Final = "http-login"

IP_BANS_FILE: Final = "ip_bans.yaml"
# Bound the reverse DNS lookup so a slow resolver cannot stall the response
REVERSE_DNS_TIMEOUT: Final = 1
ATTR_BANNED_AT: Final = "banned_at"

# A stalled resolver can take ~10s (5s x 2 retries) to give up on a PTR lookup.
# The mobile companion app gives up after 10s, so a hanging lookup turns every
# failed login into a connection timeout. Bound the lookup well below that so
# the auth response is never delayed by a lookup that only enriches a log line.
RESOLVE_HOST_TIMEOUT: Final = 1.0


# A stalled gethostbyaddr blocks the thread it runs on for ~10s (5s x 2 resolver
# retries). Running it on the shared executor would let one unresolvable IP
# starve every other executor job, so give it a dedicated thread. The holder is
# rebuilt after shutdown so a stopped instance does not leave a permanently
# unusable pool behind for the next one.
class _ResolveHostExecutor:
    """Lazily create and recreate the dedicated reverse-DNS thread pool."""

    def __init__(self) -> None:
        """Initialize the holder."""
        self._executor: ThreadPoolExecutor | None = None
        self._lookup: Future[tuple[str, list[str], list[str]]] | None = None
        self._shutdown_registered = False

    def get(self) -> ThreadPoolExecutor:
        """Return a live pool, rebuilding it if it was shut down."""
        executor = self._executor
        if executor is None or executor._shutdown:  # noqa: SLF001
            executor = self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="resolve-host"
            )
        return executor

    def submit_lookup(
        self, hass: HomeAssistant, address: str
    ) -> Future[tuple[str, list[str], list[str]]] | None:
        """Submit a reverse-DNS lookup, unless one is already running.

        A lookup that timed out cannot be cancelled, so queueing more work
        behind a stalled resolver only grows the pool queue. Skipping the
        lookup falls back to the bare IP address, same as a timeout.
        """
        if self._lookup is not None and not self._lookup.done():
            return None
        self.register_shutdown(hass)
        self._lookup = self.get().submit(gethostbyaddr, address)
        return self._lookup

    def register_shutdown(self, hass: HomeAssistant) -> None:
        """Register the stop listener the first time the pool is used.

        process_wrong_login can create the pool without setup_bans having
        run, since log_invalid_auth also works when banning is disabled,
        so the listener cannot only be registered from setup_bans.
        """
        if self._shutdown_registered:
            return
        self._shutdown_registered = True

        @callback
        def _shutdown_on_stop(_event: Any) -> None:
            """Release the dedicated reverse-DNS thread on stop."""
            self.shutdown()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_on_stop)

    def shutdown(self) -> None:
        """Release the thread."""
        self._shutdown_registered = False
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None


_resolve_host_executor = _ResolveHostExecutor()


SCHEMA_IP_BAN_ENTRY: Final = probatio.Schema(
    {probatio.Optional(ATTR_BANNED_AT, default=None): probatio.Any(None, cv.datetime)}
)


@callback
def setup_bans(hass: HomeAssistant, app: Application, login_threshold: int) -> None:
    """Create IP Ban middleware for the app."""
    app.middlewares.append(ban_middleware)
    app[KEY_FAILED_LOGIN_ATTEMPTS] = defaultdict[IPv4Address | IPv6Address, int](int)
    app[KEY_LOGIN_THRESHOLD] = login_threshold
    app[KEY_BAN_MANAGER] = IpBanManager(hass)

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

    # The lookup only enriches the log message, so it must never delay the
    # auth response. On timeout, fall back to the bare IP address.
    lookup = _resolve_host_executor.submit_lookup(hass, request.remote)
    if lookup is not None:
        with suppress(TimeoutError, OSError, UnicodeError):
            remote_host, _, _ = await asyncio.wait_for(
                asyncio.wrap_future(lookup), timeout=RESOLVE_HOST_TIMEOUT
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
            f"Too many login attempts from {remote_addr}",
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
    No release IP address from banned list function, it can only be done by
    manual modify ip bans config file.
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
        self.banned_at = banned_at or dt_util.utcnow()


class IpBanManager:
    """Manage IP bans."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the ban manager."""
        self.hass = hass
        self.path = hass.config.path(IP_BANS_FILE)
        self.ip_bans_lookup: dict[IPv4Address | IPv6Address, IpBan] = {}

    async def async_load(self) -> None:
        """Load the existing IP bans."""
        try:
            list_ = await self.hass.async_add_executor_job(
                load_yaml_config_file, self.path
            )
        except FileNotFoundError:
            return
        except HomeAssistantError as err:
            _LOGGER.error("Unable to load %s: %s", self.path, str(err))
            return

        ip_bans_lookup: dict[IPv4Address | IPv6Address, IpBan] = {}
        for ip_ban, ip_info in list_.items():
            try:
                ip_info = SCHEMA_IP_BAN_ENTRY(ip_info)
                ban = IpBan(ip_ban, ip_info["banned_at"])
                ip_bans_lookup[ban.ip_address] = ban
            except probatio.Invalid as err:
                _LOGGER.error("Failed to load IP ban %s: %s", ip_info, err)
                continue
            except ValueError:
                _LOGGER.error("Failed to load IP ban: invalid IP address %s", ip_ban)
                continue

        self.ip_bans_lookup = ip_bans_lookup

    def _add_ban(self, ip_ban: IpBan) -> None:
        """Update config file with new banned IP address."""
        with open(self.path, "a", encoding="utf8") as out:
            ip_ = {
                str(ip_ban.ip_address): {ATTR_BANNED_AT: ip_ban.banned_at.isoformat()}
            }
            # Write in a single write call to avoid interleaved writes
            out.write("\n" + yaml_util.dump(ip_))

    async def async_add_ban(self, remote_addr: IPv4Address | IPv6Address) -> None:
        """Add a new IP address to the banned list."""
        if remote_addr not in self.ip_bans_lookup:
            new_ban = self.ip_bans_lookup[remote_addr] = IpBan(remote_addr)
            try:
                await self.hass.async_add_executor_job(self._add_ban, new_ban)
            except OSError as err:
                # The ban still applies until Home Assistant restarts.
                _LOGGER.error("Unable to save the ban of %s: %s", remote_addr, err)
