"""Authentication for HTTP component."""

import base64
import hmac
import logging

from aiohttp import hdrs
from aiohttp.web import middleware
import jwt

from homeassistant.core import callback
from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.auth.providers import legacy_api_password
from homeassistant.auth.util import generate_secret
from homeassistant.util import dt as dt_util

from .const import KEY_AUTHENTICATED, KEY_REAL_IP

DATA_API_PASSWORD = 'api_password'
DATA_SIGN_SECRET = 'http.auth.sign_secret'
SIGN_QUERY_PARAM = 'authSig'

_LOGGER = logging.getLogger(__name__)


@callback
def async_sign_path(hass, refresh_token_id, path, expiration):
    """Sign a path for temporary access without auth header."""
    secret = hass.data.get(DATA_SIGN_SECRET)

    if secret is None:
        secret = hass.data[DATA_SIGN_SECRET] = generate_secret()

    now = dt_util.utcnow()
    return "{}?{}={}".format(path, SIGN_QUERY_PARAM, jwt.encode({
        'iss': refresh_token_id,
        'path': path,
        'iat': now,
        'exp': now + expiration,
    }, secret, algorithm='HS256').decode())


@callback
def setup_auth(app, trusted_networks, api_password):
    """Create auth middleware for the app."""
    old_auth_warning = set()

    @middleware
    async def auth_middleware(request, handler):
        """Authenticate as middleware."""
        authenticated = False

        if (HTTP_HEADER_HA_AUTH in request.headers or
                DATA_API_PASSWORD in request.query):
            if request.path not in old_auth_warning:
                _LOGGER.log(
                    logging.INFO if api_password else logging.WARNING,
                    'You need to use a bearer token to access %s from %s',
                    request.path, request[KEY_REAL_IP])
                old_auth_warning.add(request.path)

        if (hdrs.AUTHORIZATION in request.headers and
                await async_validate_auth_header(request, api_password)):
            # it included both use_auth and api_password Basic auth
            authenticated = True

        # We first start with a string check to avoid parsing query params
        # for every request.
        elif (request.method == "GET" and SIGN_QUERY_PARAM in request.query and
              await async_validate_signed_request(request)):
            authenticated = True

        elif (api_password and HTTP_HEADER_HA_AUTH in request.headers and
              hmac.compare_digest(
                  api_password.encode('utf-8'),
                  request.headers[HTTP_HEADER_HA_AUTH].encode('utf-8'))):
            # A valid auth header has been set
            authenticated = True
            request['hass_user'] = await legacy_api_password.async_get_user(
                app['hass'])

        elif (api_password and DATA_API_PASSWORD in request.query and
              hmac.compare_digest(
                  api_password.encode('utf-8'),
                  request.query[DATA_API_PASSWORD].encode('utf-8'))):
            authenticated = True
            request['hass_user'] = await legacy_api_password.async_get_user(
                app['hass'])

        elif _is_trusted_ip(request, trusted_networks):
            users = await app['hass'].auth.async_get_users()
            for user in users:
                if user.is_owner:
                    request['hass_user'] = user
                    break
            authenticated = True

        request[KEY_AUTHENTICATED] = authenticated
        return await handler(request)

    app.middlewares.append(auth_middleware)


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


async def async_validate_auth_header(request, api_password=None):
    """
    Test authorization header against access token.

    Basic auth_type is legacy code, should be removed with api_password.
    """
    if hdrs.AUTHORIZATION not in request.headers:
        return False

    try:
        auth_type, auth_val = \
            request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)
    except ValueError:
        # If no space in authorization header
        return False

    hass = request.app['hass']

    if auth_type == 'Bearer':
        refresh_token = await hass.auth.async_validate_access_token(auth_val)
        if refresh_token is None:
            return False

        request['hass_refresh_token'] = refresh_token
        request['hass_user'] = refresh_token.user
        return True

    if auth_type == 'Basic' and api_password is not None:
        decoded = base64.b64decode(auth_val).decode('utf-8')
        try:
            username, password = decoded.split(':', 1)
        except ValueError:
            # If no ':' in decoded
            return False

        if username != 'homeassistant':
            return False

        if not hmac.compare_digest(api_password.encode('utf-8'),
                                   password.encode('utf-8')):
            return False

        request['hass_user'] = await legacy_api_password.async_get_user(hass)
        return True

    return False


async def async_validate_signed_request(request):
    """Validate a signed request."""
    hass = request.app['hass']
    secret = hass.data.get(DATA_SIGN_SECRET)

    if secret is None:
        return False

    signature = request.query.get(SIGN_QUERY_PARAM)

    if signature is None:
        return False

    try:
        claims = jwt.decode(
            signature,
            secret,
            algorithms=['HS256'],
            options={'verify_iss': False}
        )
    except jwt.InvalidTokenError:
        return False

    if claims['path'] != request.path:
        return False

    refresh_token = await hass.auth.async_get_refresh_token(claims['iss'])

    if refresh_token is None:
        return False

    request['hass_refresh_token'] = refresh_token
    request['hass_user'] = refresh_token.user

    return True
