"""Authentication for HTTP component."""
import asyncio
import base64
import hmac
import logging

from aiohttp import hdrs
from aiohttp.web import middleware

from homeassistant.const import HTTP_HEADER_HA_AUTH
from .util import get_real_ip
from .const import KEY_TRUSTED_NETWORKS, KEY_AUTHENTICATED

DATA_API_PASSWORD = 'api_password'

_LOGGER = logging.getLogger(__name__)


@middleware
@asyncio.coroutine
def auth_middleware(request, handler):
    """Authenticate as middleware."""
    # If no password set, just always set authenticated=True
    if request.app['hass'].http.api_password is None:
        request[KEY_AUTHENTICATED] = True
        return handler(request)

    # Check authentication
    authenticated = False

    if (HTTP_HEADER_HA_AUTH in request.headers and
            validate_password(
                request, request.headers[HTTP_HEADER_HA_AUTH])):
        # A valid auth header has been set
        authenticated = True

    elif (DATA_API_PASSWORD in request.query and
          validate_password(request, request.query[DATA_API_PASSWORD])):
        authenticated = True

    elif (hdrs.AUTHORIZATION in request.headers and
          validate_authorization_header(request)):
        authenticated = True

    elif is_trusted_ip(request):
        authenticated = True

    request[KEY_AUTHENTICATED] = authenticated
    return handler(request)


def is_trusted_ip(request):
    """Test if request is from a trusted ip."""
    ip_addr = get_real_ip(request)

    return ip_addr and any(
        ip_addr in trusted_network for trusted_network
        in request.app[KEY_TRUSTED_NETWORKS])


def validate_password(request, api_password):
    """Test if password is valid."""
    return hmac.compare_digest(
        api_password, request.app['hass'].http.api_password)


def validate_authorization_header(request):
    """Test an authorization header if valid password."""
    if hdrs.AUTHORIZATION not in request.headers:
        return False

    auth_type, auth = request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)

    if auth_type != 'Basic':
        return False

    decoded = base64.b64decode(auth).decode('utf-8')
    username, password = decoded.split(':', 1)

    if username != 'homeassistant':
        return False

    return validate_password(request, password)
