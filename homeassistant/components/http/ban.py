"""Ban logic for HTTP component."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import suppress
from datetime import datetime
from http import HTTPStatus
from ipaddress import (
    IPv4Address,
    IPv6Address,
    ip_address,
    ip_network,
    AddressValueError,
    NetmaskValueError,
)
import logging
from socket import gethostbyaddr, herror
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
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.hassio import get_supervisor_ip, is_hassio
from homeassistant.util import dt as dt_util, yaml as yaml_util

from .const import KEY_HASS
from .view import HomeAssistantView

_LOGGER: Final = logging.getLogger(__name__)

KEY_BAN_MANAGER = AppKey["IpBanManager"]("ha_banned_ips_manager")
KEY_FAILED_LOGIN_ATTEMPTS = AppKey[defaultdict[IPv4Address | IPv6Address, int]](
    "ha_failed_login_attempts"
)
KEY_LOGIN_THRESHOLD = AppKey[int]("ban_manager.ip_bans_lookup")

NOTIFICATION_ID_BAN: Final = "ip-ban"
NOTIFICATION_ID_LOGIN: Final = "http-login"

IP_BANS_FILE: Final = "ip_bans.yaml"

ATTR_BANNED_AT: Final = "banned_at"
KEY_BANNED_NETWORKS: Final = "networks"
KEY_OPTIONS: Final = "options"
ATTR_NOTIFY: Final = "notify"
ATTR_LOG: Final = "log"


SCHEMA_IP_BAN_ENTRY: Final = vol.Schema(
    {vol.Optional(ATTR_BANNED_AT): vol.Any(None, cv.datetime)}
)


@callback
def setup_bans(
    hass: HomeAssistant,
    app: Application,
    login_threshold: int,
    banned_networks: list[ip_network],
    log_banned_networks: bool,
    notify_banned_networks: bool,
) -> None:
    """Create IP Ban middleware for the app."""
    app.middlewares.append(ban_middleware)
    app[KEY_FAILED_LOGIN_ATTEMPTS] = defaultdict[IPv4Address | IPv6Address, int](int)
    app[KEY_LOGIN_THRESHOLD] = login_threshold
    app[KEY_BAN_MANAGER] = IpBanManager(hass)

    async def ban_startup(app: Application) -> None:
        """Initialize bans when app starts up."""
        await app[KEY_BAN_MANAGER].async_load(
            banned_networks, log_banned_networks, notify_banned_networks
        )

    app.on_startup.append(ban_startup)


@middleware
async def ban_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """IP Ban middleware."""
    if (ban_manager := request.app.get(KEY_BAN_MANAGER)) is None:
        _LOGGER.error("IP Ban middleware loaded but banned IPs not loaded")
        return await handler(request)

    ip_address_ = ip_address(request.remote)  # type: ignore[arg-type]
    if ip_bans_lookup := ban_manager.ip_bans_lookup:
        # Verify if IP is not banned
        if ip_address_ in ip_bans_lookup:
            raise HTTPForbidden
    # Verify the whole subnet isn't banned
    if banned_networks := ban_manager.banned_networks:
        for banned_network in banned_networks:
            if ip_address_ in banned_network:
                if ban_manager.notify_bans or ban_manager.log_bans:
                    hass = ban_manager.hass
                    remote_host = request.remote
                    with suppress(herror):
                        remote_host, _, _ = await hass.async_add_executor_job(
                            gethostbyaddr, request.remote
                        )

                    base_msg = f"Prevented access attempt from {remote_host} ({ip_address_}) which is in banned network {banned_network}"
                    if ban_manager.notify_bans:
                        # Circular import with websocket_api
                        # pylint: disable=import-outside-toplevel
                        from homeassistant.components import persistent_notification

                        persistent_notification.async_create(
                            hass,
                            f"{base_msg}, see log for details",
                            "IP address blocked",
                            NOTIFICATION_ID_BAN,
                        )
                    if ban_manager.log_bans:
                        _LOGGER.warning(base_msg)
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
    remote_host = request.remote
    with suppress(herror):
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
    # pylint: disable=import-outside-toplevel
    from homeassistant.components import persistent_notification

    persistent_notification.async_create(
        hass, notification_msg, "Login attempt failed", NOTIFICATION_ID_LOGIN
    )

    # Check if ban middleware is loaded
    if KEY_BAN_MANAGER not in request.app or request.app[KEY_LOGIN_THRESHOLD] < 1:
        return

    request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] += 1

    # Supervisor IP should never be banned
    if is_hassio(hass) and str(remote_addr) == get_supervisor_ip():
        return

    if (
        request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr]
        >= request.app[KEY_LOGIN_THRESHOLD]
    ):
        ban_manager = request.app[KEY_BAN_MANAGER]
        _LOGGER.warning("Banned IP %s for too many login attempts", remote_addr)
        await ban_manager.async_add_ban(remote_addr)

        persistent_notification.async_create(
            hass,
            f"Too many login attempts from {remote_addr}",
            "Banning IP address",
            NOTIFICATION_ID_BAN,
        )


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
        self.banned_networks: list[ip_network] = []
        self.notify_bans: bool = True
        self.log_bans: bool = True

    async def async_load(
        self,
        banned_networks: list[ip_network],
        log_banned_networks: bool,
        notify_banned_networks: bool,
    ) -> None:
        """Load the existing IP bans."""
        self.banned_networks: list[ip_network]
        self.notify_bans = notify_banned_networks
        self.log_bans = log_banned_networks
        supervisor_ip = get_supervisor_ip()
        for network in banned_networks:
            try:
                network_ip_network = ip_network(network, strict=False)
                # Prevent inadvertently banning the supervisor's network
                if supervisor_ip and ip_address(supervisor_ip) in network_ip_network:
                    _LOGGER.error(
                        "Unable to ban network %s as it is used by the supervisor %s",
                        network,
                        supervisor_ip,
                    )
                else:
                    self.banned_networks.append(network_ip_network)
            except (AddressValueError, NetmaskValueError, ValueError) as err:
                _LOGGER.error(
                    "Error in banned network %s: %s. Check configuration",
                    network,
                    str(err),
                )
        _LOGGER.info(
            "Banned networks: %s, log %s, notify %s",
            str(self.banned_networks),
            self.log_bans,
            self.notify_bans,
        )

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
            except vol.Invalid as err:
                _LOGGER.error("Failed to load IP ban %s: %s", ip_info, err)
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
            await self.hass.async_add_executor_job(self._add_ban, new_ban)
