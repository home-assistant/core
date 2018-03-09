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
                    api_password, request.headers[HTTP_HEADER_HA_AUTH])):
            # A valid auth header has been set
            authenticated = True

        elif (DATA_API_PASSWORD in request.query and
              hmac.compare_digest(api_password,
                                  request.query[DATA_API_PASSWORD])):
            authenticated = True

        elif (hdrs.AUTHORIZATION in request.headers and
              validate_authorization_header(api_password, request)):
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
        api_password, request.app['hass'].http.api_password)


def validate_authorization_header(api_password, request):
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

    return hmac.compare_digest(api_password, password)
