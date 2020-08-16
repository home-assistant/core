"""Ban logic for HTTP component."""
from collections import defaultdict
from datetime import datetime
from ipaddress import ip_address
import logging
from typing import List, Optional

from aiohttp.web import middleware
from aiohttp.web_exceptions import HTTPForbidden, HTTPUnauthorized
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import HTTP_BAD_REQUEST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.util.yaml import dump

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

KEY_BANNED_IPS = "ha_banned_ips"
KEY_FAILED_LOGIN_ATTEMPTS = "ha_failed_login_attempts"
KEY_LOGIN_THRESHOLD = "ha_login_threshold"

NOTIFICATION_ID_BAN = "ip-ban"
NOTIFICATION_ID_LOGIN = "http-login"

IP_BANS_FILE = "ip_bans.yaml"
ATTR_BANNED_AT = "banned_at"

SCHEMA_IP_BAN_ENTRY = vol.Schema(
    {vol.Optional("banned_at"): vol.Any(None, cv.datetime)}
)


@callback
def setup_bans(hass, app, login_threshold):
    """Create IP Ban middleware for the app."""
    app.middlewares.append(ban_middleware)
    app[KEY_FAILED_LOGIN_ATTEMPTS] = defaultdict(int)
    app[KEY_LOGIN_THRESHOLD] = login_threshold

    async def ban_startup(app):
        """Initialize bans when app starts up."""
        app[KEY_BANNED_IPS] = await async_load_ip_bans_config(
            hass, hass.config.path(IP_BANS_FILE)
        )

    app.on_startup.append(ban_startup)


@middleware
async def ban_middleware(request, handler):
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


def log_invalid_auth(func):
    """Decorate function to handle invalid auth or failed login attempts."""

    async def handle_req(view, request, *args, **kwargs):
        """Try to log failed login attempts if response status >= 400."""
        resp = await func(view, request, *args, **kwargs)
        if resp.status >= HTTP_BAD_REQUEST:
            await process_wrong_login(request)
        return resp

    return handle_req


async def process_wrong_login(request):
    """Process a wrong login attempt.

    Increase failed login attempts counter for remote IP address.
    Add ip ban entry if failed login attempts exceeds threshold.
    """
    remote_addr = ip_address(request.remote)

    msg = f"Login attempt or request with invalid authentication from {remote_addr}"
    _LOGGER.warning(msg)

    hass = request.app["hass"]
    hass.components.persistent_notification.async_create(
        msg, "Login attempt failed", NOTIFICATION_ID_LOGIN
    )

    # Check if ban middleware is loaded
    if KEY_BANNED_IPS not in request.app or request.app[KEY_LOGIN_THRESHOLD] < 1:
        return

    request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] += 1

    # Supervisor IP should never be banned
    if "hassio" in hass.config.components and hass.components.hassio.get_supervisor_ip() == str(
        remote_addr
    ):
        return

    if (
        request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr]
        >= request.app[KEY_LOGIN_THRESHOLD]
    ):
        new_ban = IpBan(remote_addr)
        request.app[KEY_BANNED_IPS].append(new_ban)

        await hass.async_add_job(
            update_ip_bans_config, hass.config.path(IP_BANS_FILE), new_ban
        )

        _LOGGER.warning("Banned IP %s for too many login attempts", remote_addr)

        hass.components.persistent_notification.async_create(
            f"Too many login attempts from {remote_addr}",
            "Banning IP address",
            NOTIFICATION_ID_BAN,
        )


async def process_success_login(request):
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

    def __init__(self, ip_ban: str, banned_at: Optional[datetime] = None) -> None:
        """Initialize IP Ban object."""
        self.ip_address = ip_address(ip_ban)
        self.banned_at = banned_at or datetime.utcnow()


async def async_load_ip_bans_config(hass: HomeAssistant, path: str) -> List[IpBan]:
    """Load list of banned IPs from config file."""
    ip_list: List[IpBan] = []

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
        ip_ = {
            str(ip_ban.ip_address): {
                ATTR_BANNED_AT: ip_ban.banned_at.strftime("%Y-%m-%dT%H:%M:%S")
            }
        }
        out.write("\n")
        out.write(dump(ip_))
