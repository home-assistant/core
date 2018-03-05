"""Authentication for HTTP component."""
import base64
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta

import voluptuous as vol
from aiohttp import hdrs
from aiohttp.web import middleware
from pytz import utc as tz_utc

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.config import async_log_exception, load_yaml_config_file
from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.yaml import dump

from .const import CLIENT_ID, CLIENT_SECRET, KEY_AUTHENTICATED, KEY_REAL_IP

YAML_SECRETS = 'auth_secrets.yaml'

DATA_API_PASSWORD = 'api_password'

DATETIME_FORMAT = '%Y%m%dT%H%M%SZ'
DATE_FORMAT = '%Y%m%d'

_LOGGER = logging.getLogger(__name__)


@callback
def setup_auth(hass, app, trusted_networks, api_password):
    """Create auth middleware for the app."""

    @middleware
    async def auth_middleware(request, handler):
        """Authenticate as middleware."""
        # If no password set, just always set authenticated=True
        if api_password is None:
            request[KEY_AUTHENTICATED] = True
            return (await handler(request))

        # Check authentication
        authenticated = False

        if (HTTP_HEADER_HA_AUTH in request.headers and
                hmac.compare_digest(
                    api_password, request.headers[HTTP_HEADER_HA_AUTH])):
            # A valid auth header has been set
            authenticated = True

        elif (DATA_API_PASSWORD in request.query and
              hmac.compare_digest(api_password,
                                  request.query[DATA_API_PASSWORD])):
            authenticated = True

        elif _is_trusted_ip(request, trusted_networks):
            authenticated = True

        elif (hdrs.AUTHORIZATION in request.headers):
            authenticated = validate_authorization_header(
                api_password, request, auth)

        request[KEY_AUTHENTICATED] = authenticated
        return (await handler(request))

    auth = Auth(hass)

    async def auth_startup(app):
        """Initialize auth middleware when app starts up."""

        app.middlewares.append(auth_middleware)
        await auth.startup()

    app.on_startup.append(auth_startup)

    return auth


def _is_trusted_ip(request, trusted_networks):
    """Test if request is from a trusted ip."""
    ip_addr = request[KEY_REAL_IP]

    return any(
        ip_addr in trusted_network for trusted_network
        in trusted_networks)


def validate_password(request, api_password):
    """Test if password is valid."""
    return hmac.compare_digest(
        api_password, request.app['hass'].http.api_password)


def validate_authorization_header(api_password, request, auth_obj):
    """Test an authorization header if valid password."""
    if hdrs.AUTHORIZATION not in request.headers:
        return False

    auth_type, auth = request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)

    if auth_obj.hmac.do_auth_hmac(request, auth_type, auth):
        return True

    if auth_type != 'Basic':
        return False

    decoded = base64.b64decode(auth).decode('utf-8')
    username, password = decoded.split(':', 1)

    if username != 'homeassistant':
        return False

    return hmac.compare_digest(api_password, password)


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
                result[client[CLIENT_ID]] = HmacClient(
                    client['name'], client[CLIENT_ID], client[CLIENT_SECRET])
        return result
    except (HomeAssistantError, FileNotFoundError):
        # When YAML file could not be loaded/did not contain a dict
        return []


# StringToHash:
# <method>\n
# <uri>\n
# <query string sorted>\n
# <%Y%m%dT%H%M%SZ>\n
# <header sorted empty for now>\n
# <if post body hash hex or ''>

# Key:
# hmac(key=<secret>, msg=<date YYYYMMDD>), hex digest

# string: UTF8 Encoding
# hash: URL safe base64 encoding
# need more discuss to consider include headers
def genStrToHash(method: str, uri: str, qs: str, ts: str,
                 header: str = '', bodyhash: str = ''):
    """Generate string to hash"""
    str1 = '\n'.join([method, uri, sortQueryString(qs), ts,
                      header, bodyhash])
    return str1


def sortQueryString(qs: str):
    """Sort Query String by alphabet"""
    qs1 = qs.split('&')
    qs1.sort()
    return '&'.join(qs1)


def format_time(input: datetime = None):
    """Format time for HMAC"""
    if not input:
        input = dt_util.utcnow()
    else:
        input = dt_util.as_utc(input)
    return input.strftime(DATETIME_FORMAT)


def parse_time(timestr: str):
    """Parse time formatted for HMAC"""
    return datetime(*(time.strptime(timestr, DATETIME_FORMAT)[0:6]),
                    tzinfo=tz_utc)


def delta_time(time1: datetime, time2: datetime = None):
    """Calculate time delta from time1 to time2 (now if None given)"""
    if not time2:
        time2 = dt_util.utcnow()
    total_seconds = (time1 - time2).total_seconds()
    return abs(total_seconds)


class HmacClient:
    """Represent a client id."""

    __slots__ = ('hass', 'name', 'id', 'secret', 'last_seen', 'hmac_date',
                 'hmac_new', 'hmac_old')

    def __init__(self, name: str, client_id: str,
                 client_secret: str) -> None:
        """Initialize a client."""
        self.name = name
        self.id = client_id
        self.secret = client_secret
        self.hmac_date = None

    def digest(self, ts, msg):
        """Calculate HMAC digest"""
        if not ts or delta_time(ts) > 300:
            return False

        c_date = ts.date()

        hmac_obj = None

        if (self.hmac_date is None or
                self.hmac_date - c_date > timedelta(days=1)):
            self.hmac_date = c_date

            datestr = (c_date - timedelta(days=1)).strftime(DATE_FORMAT)
            key1 = hmac.new(self.secret.encode(), datestr.encode()).hexdigest()
            self.hmac_old = hmac.new(key1.encode())

            datestr = c_date.strftime(DATE_FORMAT)
            key1 = hmac.new(self.secret.encode(), datestr.encode()).hexdigest()
            self.hmac_new = hmac.new(key1.encode())

            hmac_obj = self.hmac_new

        elif c_date > self.hmac_date:
            self.hmac_old = self.hmac_new

            datestr = c_date.strftime(DATE_FORMAT)
            key1 = hmac.new(self.secret.encode(), datestr.encode()).hexdigest()
            self.hmac_new = hmac.new(key1.encode())

            hmac_obj = self.hmac_new

        elif c_date < self.hmac_date:
            hmac_obj = self.hmac_old

        else:
            hmac_obj = self.hmac_new

        if isinstance(msg, str):
            msg = msg.encode()

        hmac_obj = hmac_obj.copy()
        hmac_obj.update(msg)
        hashed = hmac_obj.digest()

        # b64hashed = base64.urlsafe_b64encode(hashed)
        return hashed


class AuthHmac(object):
    def __init__(self, hass):
        self.yaml_path = hass.config.path(YAML_SECRETS)
        self.hass = hass
        # self.load_config()

    async def new_api(self, name: str):
        """Create new API key and save to YAML configuration file."""
        if not self.clients:
            return None

        while True:
            c_id = secrets.token_urlsafe(12)
            if c_id not in self.clients:
                break

        c_secret = secrets.token_urlsafe(32)
        with open(self.yaml_path, 'a') as out:
            device = {name: {
                CLIENT_ID: c_id,
                CLIENT_SECRET: c_secret,
            }}
            out.write('\n')
            out.write(dump(device))

        return HmacClient(name, c_id, c_secret)

    async def load_config(self):
        self.clients = await async_load_config(self.yaml_path, self.hass)

    async def startup(self):
        await self.load_config()

    def do_auth_hmac(self, request, auth_type, auth):
        """Process HTTP auth"""
        if auth_type != 'HA-HMAC-MD5':
            return False

        uri = request.url.path
        method = request.method
        qs = request.query_string
        # method.lower()

        c_id, c_ts, c_hmac = auth.split(':')

        client = self.clients[c_id]

        if not client:
            return False

        c_time = parse_time(c_ts)
        if delta_time(c_time) > 300:
            return False

        strToHash = genStrToHash(method, uri, qs, c_ts)
        hashed = client.digest(c_time, strToHash)

        orighashed = base64.urlsafe_b64decode(c_hmac.encode())

        return hashed == orighashed


class Auth(object):
    __slots__ = ('hass', 'hmac')

    def __init__(self, hass):
        self.hass = hass
        self.hmac = AuthHmac(hass)

    async def startup(self):
        await self.hmac.startup()
