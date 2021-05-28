"""Ban logic for HTTP component."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime
from ipaddress import ip_address
import logging
from socket import gethostbyaddr, herror
from typing import Any, Final

from aiohttp.web import Application, Request, StreamResponse, middleware
from aiohttp.web_exceptions import HTTPForbidden, HTTPUnauthorized
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import HTTP_BAD_REQUEST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util, yaml

from .view import HomeAssistantView

_LOGGER: Final = logging.getLogger(__name__)

KEY_BANNED_IPS: Final = "ha_banned_ips"
KEY_FAILED_LOGIN_ATTEMPTS: Final = "ha_failed_login_attempts"
KEY_LOGIN_THRESHOLD: Final = "ha_login_threshold"

NOTIFICATION_ID_BAN: Final = "ip-ban"
NOTIFICATION_ID_LOGIN: Final = "http-login"

IP_BANS_FILE: Final = "ip_bans.yaml"
ATTR_BANNED_AT: Final = "banned_at"

SCHEMA_IP_BAN_ENTRY: Final = vol.Schema(
    {vol.Optional("banned_at"): vol.Any(None, cv.datetime)}
)


@callback
def setup_bans(hass: HomeAssistant, app: Application, login_threshold: int) -> None:
    """Create IP Ban middleware for the app."""
    app.middlewares.append(ban_middleware)
    app[KEY_FAILED_LOGIN_ATTEMPTS] = defaultdict(int)
    app[KEY_LOGIN_THRESHOLD] = login_threshold

    async def ban_startup(app: Application) -> None:
        """Initialize bans when app starts up."""
        app[KEY_BANNED_IPS] = await async_load_ip_bans_config(
            hass, hass.config.path(IP_BANS_FILE)
        )

    app.on_startup.append(ban_startup)


@middleware
async def ban_middleware(
    request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
) -> StreamResponse:
    """IP Ban middleware."""
    if KEY_BANNED_IPS not in request.app:
        _LOGGER.error("IP Ban middleware loaded but banned IPs not loaded")
        return await handler(request)

    # Verify if IP is not banned
    ip_address_ = ip_address(request.remote)
    is_banned = any(
        ip_ban.ip_address == ip_address_ for ip_ban in request.app[KEY_BANNED_IPS]
    )

    if is_banned:
        raise HTTPForbidden()

    try:
        return await handler(request)
    except HTTPUnauthorized:
        await process_wrong_login(request)
        raise


def log_invalid_auth(
    func: Callable[..., Awaitable[StreamResponse]]
) -> Callable[..., Awaitable[StreamResponse]]:
    """Decorate function to handle invalid auth or failed login attempts."""

    async def handle_req(
        view: HomeAssistantView, request: Request, *args: Any, **kwargs: Any
    ) -> StreamResponse:
        """Try to log failed login attempts if response status >= 400."""
        resp = await func(view, request, *args, **kwargs)
        if resp.status >= HTTP_BAD_REQUEST:
            await process_wrong_login(request)
        return resp

    return handle_req


async def process_wrong_login(request: Request) -> None:
    """Process a wrong login attempt.

    Increase failed login attempts counter for remote IP address.
    Add ip ban entry if failed login attempts exceeds threshold.
    """
    hass = request.app["hass"]

    remote_addr = ip_address(request.remote)
    remote_host = request.remote
    with suppress(herror):
        remote_host, _, _ = await hass.async_add_executor_job(
            gethostbyaddr, request.remote
        )

    base_msg = f"Login attempt or request with invalid authentication from {remote_host} ({remote_addr})."

    # The user-agent is unsanitized input so we only include it in the log
    user_agent = request.headers.get("user-agent")
    log_msg = f"{base_msg} ({user_agent})"

    notification_msg = f"{base_msg} See the log for details."

    _LOGGER.warning(log_msg)
    # AIS fix
    # hass.components.persistent_notification.async_create(
    #     notification_msg, "Login attempt failed", NOTIFICATION_ID_LOGIN
    # )

    # Check if ban middleware is loaded
    if KEY_BANNED_IPS not in request.app or request.app[KEY_LOGIN_THRESHOLD] < 1:
        return

    request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] += 1

    # Supervisor IP should never be banned
    if (
        "hassio" in hass.config.components
        and hass.components.hassio.get_supervisor_ip() == str(remote_addr)
    ):
        return

    if (
        request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr]
        >= request.app[KEY_LOGIN_THRESHOLD]
    ):
        new_ban = IpBan(remote_addr)
        request.app[KEY_BANNED_IPS].append(new_ban)

        await hass.async_add_executor_job(
            update_ip_bans_config, hass.config.path(IP_BANS_FILE), new_ban
        )

        _LOGGER.warning("Banned IP %s for too many login attempts", remote_addr)

        hass.components.persistent_notification.async_create(
            f"Too many login attempts from {remote_addr}",
            "Banning IP address",
            NOTIFICATION_ID_BAN,
        )


async def process_success_login(request: Request) -> None:
    """Process a success login attempt.

    Reset failed login attempts counter for remote IP address.
    No release IP address from banned list function, it can only be done by
    manual modify ip bans config file.
    """
    remote_addr = ip_address(request.remote)

    # Check if ban middleware is loaded
    if KEY_BANNED_IPS not in request.app or request.app[KEY_LOGIN_THRESHOLD] < 1:
        return

    if (
        remote_addr in request.app[KEY_FAILED_LOGIN_ATTEMPTS]
        and request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] > 0
    ):
        _LOGGER.debug(
            "Login success, reset failed login attempts counter from %s", remote_addr
        )
        request.app[KEY_FAILED_LOGIN_ATTEMPTS].pop(remote_addr)


class IpBan:
    """Represents banned IP address."""

    def __init__(self, ip_ban: str, banned_at: datetime | None = None) -> None:
        """Initialize IP Ban object."""
        self.ip_address = ip_address(ip_ban)
        self.banned_at = banned_at or dt_util.utcnow()


async def async_load_ip_bans_config(hass: HomeAssistant, path: str) -> list[IpBan]:
    """Load list of banned IPs from config file."""
    ip_list: list[IpBan] = []

    try:
        list_ = await hass.async_add_executor_job(load_yaml_config_file, path)
    except FileNotFoundError:
        return ip_list
    except HomeAssistantError as err:
        _LOGGER.error("Unable to load %s: %s", path, str(err))
        return ip_list

    for ip_ban, ip_info in list_.items():
        try:
            ip_info = SCHEMA_IP_BAN_ENTRY(ip_info)
            ip_list.append(IpBan(ip_ban, ip_info["banned_at"]))
        except vol.Invalid as err:
            _LOGGER.error("Failed to load IP ban %s: %s", ip_info, err)
            continue

    return ip_list


def update_ip_bans_config(path: str, ip_ban: IpBan) -> None:
    """Update config file with new banned IP address."""
    with open(path, "a") as out:
        ip_ = {str(ip_ban.ip_address): {ATTR_BANNED_AT: ip_ban.banned_at.isoformat()}}
        out.write("\n")
        out.write(yaml.dump(ip_))
