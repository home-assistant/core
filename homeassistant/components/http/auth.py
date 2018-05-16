"""Authentication for HTTP component."""

import base64
import hmac
import logging

from aiohttp import hdrs
from aiohttp.web import middleware

from homeassistant.core import callback
from homeassistant.const import HTTP_HEADER_HA_AUTH
from .const import KEY_AUTHENTICATED, KEY_REAL_IP

DATA_API_PASSWORD = 'api_password'

_LOGGER = logging.getLogger(__name__)


@callback
def setup_auth(app, trusted_networks, api_password):
    """Create auth middleware for the app."""
    @middleware
    async def auth_middleware(request, handler):
        """Authenticate as middleware."""
        # If no password set, just always set authenticated=True
        if api_password is None:
            request[KEY_AUTHENTICATED] = True
            return await handler(request)

        # Check authentication
        authenticated = False

        if (HTTP_HEADER_HA_AUTH in request.headers and
                hmac.compare_digest(
                    api_password.encode('utf-8'),
                    request.headers[HTTP_HEADER_HA_AUTH].encode('utf-8'))):
            # A valid auth header has been set
            authenticated = True

        elif (DATA_API_PASSWORD in request.query and
              hmac.compare_digest(
                  api_password.encode('utf-8'),
                  request.query[DATA_API_PASSWORD].encode('utf-8'))):
            authenticated = True

        elif (hdrs.AUTHORIZATION in request.headers and
              await async_validate_auth_header(api_password, request)):
            authenticated = True

        elif _is_trusted_ip(request, trusted_networks):
            authenticated = True

        request[KEY_AUTHENTICATED] = authenticated
        return await handler(request)

    async def auth_startup(app):
        """Initialize auth middleware when app starts up."""
        app.middlewares.append(auth_middleware)

    app.on_startup.append(auth_startup)


def _is_trusted_ip(request, trusted_networks):
    """Test if request is from a trusted ip."""
    ip_addr = request[KEY_REAL_IP]

    return any(
        ip_addr in trusted_network for trusted_network
        in trusted_networks)


def validate_password(request, api_password):
    """Test if password is valid."""
    return hmac.compare_digest(
        api_password.encode('utf-8'),
        request.app['hass'].http.api_password.encode('utf-8'))


async def async_validate_auth_header(api_password, request):
    """Test an authorization header if valid password."""
    if hdrs.AUTHORIZATION not in request.headers:
        return False

    try:
        auth_type, auth_val = \
            request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)
    except ValueError:
        # If no space in authorization header
        return False

    if auth_type == 'Basic':
        decoded = base64.b64decode(auth_val).decode('utf-8')
        try:
            username, password = decoded.split(':', 1)
        except ValueError:
            # If no ':' in decoded
            return False

        if username != 'homeassistant':
            return False

        return hmac.compare_digest(api_password.encode('utf-8'),
                                   password.encode('utf-8'))

    if auth_type != 'Bearer':
        return False

    hass = request.app['hass']
    access_token = hass.auth.async_get_access_token(auth_val)
    if access_token is None:
        return False

    request['hass_user'] = access_token.refresh_token.user
    return True
