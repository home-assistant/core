"""Authentication for HTTP component."""
import asyncio
import base64
import hmac
import logging

from aiohttp import hdrs

from homeassistant.const import HTTP_HEADER_HA_AUTH, CONF_PASSWORD
from .util import get_real_ip
from .const import KEY_TRUSTED_NETWORKS, KEY_AUTHENTICATED

DATA_API_PASSWORD = 'api_password'

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def auth_middleware(app, handler):
    """Authenticate as middleware."""
    # If no password set, just always set authenticated=True
    if ((app['hass'].http.api_password is None)
            and (app['hass'].http.api_users is None)):
        @asyncio.coroutine
        def no_auth_middleware_handler(request):
            """Auth middleware to approve all requests."""
            request[KEY_AUTHENTICATED] = True
            return handler(request)

        return no_auth_middleware_handler

    @asyncio.coroutine
    def auth_middleware_handler(request):
        """Auth middleware to check authentication."""
        # Auth code verbose on purpose
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

    return auth_middleware_handler


def is_trusted_ip(request):
    """Test if request is from a trusted ip."""
    ip_addr = get_real_ip(request)

    return ip_addr and any(
        ip_addr in trusted_network for trusted_network
        in request.app[KEY_TRUSTED_NETWORKS])


def validate_password(request, api_password):
    """
    Test if one of the passwords is valid.

    First try the http.api_password, then the http.api_users' api_passwords.
    """
    validated = False
    if request.app['hass'].http.api_password:
        validated = hmac.compare_digest(
            api_password, request.app['hass'].http.api_password)
    if validated:
        _LOGGER.debug("validation with old-style api_password was successful.")
        return validated
    if request.app['hass'].http.api_users is not None:
        for username, api_user in request.app['hass'].http.api_users.items():
            validated = hmac.compare_digest(
                api_password, api_user[CONF_PASSWORD])
            if validated:
                _LOGGER.debug("validation using new api for [%s]", username)
                break
    return validated


def validate_username_password(request, username, api_password):
    """
    Test if one of the passwords with username is valid.

    First try the http.api_password, then the http.api_users' api_passwords.
    """
    validated = False
    if username == 'homeassistant':
        validated = hmac.compare_digest(
            api_password, request.app['hass'].http.api_password)
    if validated:
        _LOGGER.debug("validation with old-style api_password was successful.")
        return validated
    if request.app['hass'].http.api_users is not None:
        if username in request.app['hass'].http.api_users:
            validated = hmac.compare_digest(
                api_password,
                request.app['hass'].http.api_users[username][CONF_PASSWORD])
            if validated:
                _LOGGER.debug("validation for [%s]", username)
    return validated


def validate_authorization_header(request):
    """Test an authorization header if valid password."""
    if hdrs.AUTHORIZATION not in request.headers:
        return False

    auth_type, auth = request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)

    if auth_type != 'Basic':
        return False

    decoded = base64.b64decode(auth).decode('utf-8')
    username, password = decoded.split(':', 1)
    return validate_username_password(request, username, password)
