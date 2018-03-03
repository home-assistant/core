"""Authentication HMAC for HTTP component."""
import asyncio
import base64
import hmac
import logging
from datetime import datetime, timedelta
import time

import voluptuous as vol
from aiohttp import hdrs
from aiohttp.web import middleware

import homeassistant.helpers.config_validation as cv
import homeassistant.util as util
import homeassistant.util.dt as dt_util
from homeassistant.components import group, zone
from homeassistant.config import async_log_exception, load_yaml_config_file
from homeassistant.const import (ATTR_ENTITY_ID, ATTR_GPS_ACCURACY, ATTR_ICON,
                                 ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ICON,
                                 CONF_MAC, CONF_NAME, DEVICE_DEFAULT_NAME,
                                 HTTP_HEADER_HA_AUTH, STATE_HOME,
                                 STATE_NOT_HOME)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.helpers.typing import ConfigType, GPSType, HomeAssistantType
from homeassistant.loader import bind_hass, get_component
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.util.async import run_coroutine_threadsafe
from homeassistant.util.yaml import dump
from tzinfo import utc as tz_utc

from .const import CLIENT_ID, CLIENT_SECRET, KEY_AUTHENTICATED, KEY_REAL_IP

YAML_SECRETS = 'auth_secrets.yaml'

_LOGGER = logging.getLogger(__name__)


class Client:
    """Represent a client id."""

    last_seen = None  # type: dt_util.dt.datetime

    def __init__(self, hass, name: str, client_id: str,
                 client_secret: str) -> None:
        """Initialize a device."""
        self.hass = hass
        self.name = name
        self.id = client_id
        self.secret = client_secret

    def auth(self, a, b):
        return True


def add_secret():
    pass


def reload():
    pass


TIME_FORMAT = '%Y%m%dT%H%M%SZ'


async def async_load_config(path: str, hass: HomeAssistantType):
    """Load devices from YAML configuration file.

    This method is a coroutine.
    """
    dev_schema = vol.Schema({
        # vol.Required(CONF_NAME): cv.string,
        vol.Required(CLIENT_ID): vol.Any(None, cv.string),
        vol.Required(CLIENT_SECRET): vol.Any(None, cv.string),
    })
    try:
        result = {}
        try:
            clients = await hass.async_add_job(
                load_yaml_config_file, path)
        except HomeAssistantError as err:
            _LOGGER.error("Unable to load %s: %s", path, str(err))
            return []

        for client_name, client in clients.items():
            try:
                client = dev_schema(client)
                client['name'] = cv.slugify(client_name)
            except vol.Invalid as exp:
                async_log_exception(exp, client_name, clients, hass)
            else:
                result[client[CLIENT_ID]] = Client(hass, **client)
        return result
    except (HomeAssistantError, FileNotFoundError):
        # When YAML file could not be loaded/did not contain a dict
        return []


# StringToHash:
# <method>\n
# <uri with query string>\n
# <%Y%m%dT%H%M%SZ>\n
# <if post body hash>
# UTF8 Encoding
# URL safe base64 encoding
# need more discuss to consider include headers
def genBytesToHash(method: str, uri: str, ts: str, bodyhash: str = ''):
    str1 = '\n'.join([method, uri, ts, bodyhash])
    return str1.encode()


def setup_auth_hmac(hass: HomeAssistantType, app):
    def format_time(input: datetime = None):
        if not input:
            input = dt_util.utcnow()
        else:
            input = dt_util.as_utc(input)
        return input.strftime(TIME_FORMAT)

    def parse_time(timestr: str):
        try:
            dt = datetime(*(time.strptime(timestr, TIME_FORMAT)[0:6]),
                          tzinfo=tz_utc)
            return dt
        except ValueError:
            return None

    def delta_time(time1: datetime, time2: datetime = None):
        if not time2:
            time2 = dt_util.utcnow()
        total_seconds = (time1 - time2).total_seconds()
        return abs(total_seconds)

    async def update_config(path: str, name: str, client_id: str,
                            client_secret: str):
        """Add device to YAML configuration file."""
        with open(path, 'a') as out:
            device = {name: {
                CLIENT_ID: client_id,
                CLIENT_SECRET: client_secret,
            }}
            out.write('\n')
            out.write(dump(device))

    yaml_path = hass.config.path(YAML_SECRETS)
    clients = async_load_config(yaml_path, hass)

    def do_auth_hmac(request, auth_type, auth):
        uri = request.url.path
        method = request.method

        if auth_type != 'HA-HMAC-MD5':
            return False
        c_id, c_ts, c_hmac = auth.split(':')
        c_time = parse_time(c_ts)

        if delta_time(c_time) > 30:
            return False

        client = clients[c_id]

        if not client:
            return False

        # hmac_obj = client.hmac
        # if not hmac_obj:
        #     hmac_obj = client.hmac = hmac.new(client.secret)

        bytesToHash = genBytesToHash(method, uri, c_ts)
        hashed = hmac.new(client.secret, bytesToHash).digest()
        b64hashed = base64.urlsafe_b64encode(hashed)

        return True

    return do_auth_hmac
