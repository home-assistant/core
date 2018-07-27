"""Ban logic for HTTP component."""

from collections import defaultdict
from datetime import datetime
from ipaddress import ip_address
import logging
import os

from aiohttp.web import middleware
from aiohttp.web_exceptions import HTTPForbidden, HTTPUnauthorized
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import persistent_notification
from homeassistant.config import load_yaml_config_file
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.util.yaml import dump
from .const import KEY_REAL_IP

_LOGGER = logging.getLogger(__name__)

KEY_BANNED_IPS = 'ha_banned_ips'
KEY_FAILED_LOGIN_ATTEMPTS = 'ha_failed_login_attempts'
KEY_LOGIN_THRESHOLD = 'ha_login_threshold'

NOTIFICATION_ID_BAN = 'ip-ban'
NOTIFICATION_ID_LOGIN = 'http-login'

IP_BANS_FILE = 'ip_bans.yaml'
ATTR_BANNED_AT = "banned_at"

SCHEMA_IP_BAN_ENTRY = vol.Schema({
    vol.Optional('banned_at'): vol.Any(None, cv.datetime)
})


@callback
def setup_bans(hass, app, login_threshold):
    """Create IP Ban middleware for the app."""
    async def ban_startup(app):
        """Initialize bans when app starts up."""
        app.middlewares.append(ban_middleware)
        app[KEY_BANNED_IPS] = await hass.async_add_job(
            load_ip_bans_config, hass.config.path(IP_BANS_FILE))
        app[KEY_FAILED_LOGIN_ATTEMPTS] = defaultdict(int)
        app[KEY_LOGIN_THRESHOLD] = login_threshold

    app.on_startup.append(ban_startup)


@middleware
async def ban_middleware(request, handler):
    """IP Ban middleware."""
    if KEY_BANNED_IPS not in request.app:
        _LOGGER.error('IP Ban middleware loaded but banned IPs not loaded')
        return await handler(request)

    # Verify if IP is not banned
    ip_address_ = request[KEY_REAL_IP]
    is_banned = any(ip_ban.ip_address == ip_address_
                    for ip_ban in request.app[KEY_BANNED_IPS])

    if is_banned:
        raise HTTPForbidden()

    try:
        return await handler(request)
    except HTTPUnauthorized:
        await process_wrong_login(request)
        raise


async def process_wrong_login(request):
    """Process a wrong login attempt.

    Increase failed login attempts counter for remote IP address.
    Add ip ban entry if failed login attempts exceeds threshold.
    """
    remote_addr = request[KEY_REAL_IP]

    msg = ('Login attempt or request with invalid authentication '
           'from {}'.format(remote_addr))
    _LOGGER.warning(msg)
    persistent_notification.async_create(
        request.app['hass'], msg, 'Login attempt failed',
        NOTIFICATION_ID_LOGIN)

    # Check if ban middleware is loaded
    if (KEY_BANNED_IPS not in request.app or
            request.app[KEY_LOGIN_THRESHOLD] < 1):
        return

    request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] += 1

    if (request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] >
            request.app[KEY_LOGIN_THRESHOLD]):
        new_ban = IpBan(remote_addr)
        request.app[KEY_BANNED_IPS].append(new_ban)

        hass = request.app['hass']
        await hass.async_add_job(
            update_ip_bans_config, hass.config.path(IP_BANS_FILE), new_ban)

        _LOGGER.warning(
            "Banned IP %s for too many login attempts", remote_addr)

        persistent_notification.async_create(
            hass,
            'Too many login attempts from {}'.format(remote_addr),
            'Banning IP address', NOTIFICATION_ID_BAN)


async def process_success_login(request):
    """Process a success login attempt.

    Reset failed login attempts counter for remote IP address.
    No release IP address from banned list function, it can only be done by
    manual modify ip bans config file.
    """
    remote_addr = request[KEY_REAL_IP]

    # Check if ban middleware is loaded
    if (KEY_BANNED_IPS not in request.app or
            request.app[KEY_LOGIN_THRESHOLD] < 1):
        return

    if remote_addr in request.app[KEY_FAILED_LOGIN_ATTEMPTS] and \
            request.app[KEY_FAILED_LOGIN_ATTEMPTS][remote_addr] > 0:
        _LOGGER.debug('Login success, reset failed login attempts counter'
                      ' from %s', remote_addr)
        request.app[KEY_FAILED_LOGIN_ATTEMPTS].pop(remote_addr)


class IpBan:
    """Represents banned IP address."""

    def __init__(self, ip_ban: str, banned_at: datetime = None) -> None:
        """Initialize IP Ban object."""
        self.ip_address = ip_address(ip_ban)
        self.banned_at = banned_at or datetime.utcnow()


def load_ip_bans_config(path: str):
    """Load list of banned IPs from config file."""
    ip_list = []

    if not os.path.isfile(path):
        return ip_list

    try:
        list_ = load_yaml_config_file(path)
    except HomeAssistantError as err:
        _LOGGER.error('Unable to load %s: %s', path, str(err))
        return ip_list

    for ip_ban, ip_info in list_.items():
        try:
            ip_info = SCHEMA_IP_BAN_ENTRY(ip_info)
            ip_list.append(IpBan(ip_ban, ip_info['banned_at']))
        except vol.Invalid as err:
            _LOGGER.error("Failed to load IP ban %s: %s", ip_info, err)
            continue

    return ip_list


def update_ip_bans_config(path: str, ip_ban: IpBan):
    """Update config file with new banned IP address."""
    with open(path, 'a') as out:
        ip_ = {str(ip_ban.ip_address): {
            ATTR_BANNED_AT: ip_ban.banned_at.strftime("%Y-%m-%dT%H:%M:%S")
        }}
        out.write('\n')
        out.write(dump(ip_))
