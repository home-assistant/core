"""Authentication for HTTP component."""
import base64
import logging

from aiohttp import hdrs
from aiohttp.web import middleware
import jwt

from homeassistant.auth.providers import legacy_api_password
from homeassistant.auth.util import generate_secret
from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import (
    KEY_AUTHENTICATED,
    KEY_HASS_USER,
    KEY_REAL_IP,
)

_LOGGER = logging.getLogger(__name__)

DATA_API_PASSWORD = 'api_password'
DATA_SIGN_SECRET = 'http.auth.sign_secret'
SIGN_QUERY_PARAM = 'authSig'


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
def setup_auth(hass, app):
    """Create auth middleware for the app."""
    old_auth_warning = set()

    support_legacy = hass.auth.support_legacy
    if support_legacy:
        _LOGGER.warning("legacy_api_password support has been enabled.")

    trusted_networks = []
    for prv in hass.auth.auth_providers:
        if prv.type == 'trusted_networks':
            trusted_networks += prv.trusted_networks

    async def async_validate_auth_header(request):
        """
        Test authorization header against access token.

        Basic auth_type is legacy code, should be removed with api_password.
        """
        try:
            auth_type, auth_val = \
                request.headers.get(hdrs.AUTHORIZATION).split(' ', 1)
        except ValueError:
            # If no space in authorization header
            return False

        if auth_type == 'Bearer':
            refresh_token = await hass.auth.async_validate_access_token(
                auth_val)
            if refresh_token is None:
                return False

            request[KEY_HASS_USER] = refresh_token.user
            return True

        if auth_type == 'Basic' and support_legacy:
            decoded = base64.b64decode(auth_val).decode('utf-8')
            try:
                username, password = decoded.split(':', 1)
            except ValueError:
                # If no ':' in decoded
                return False

            if username != 'homeassistant':
                return False

            user = await legacy_api_password.async_validate_password(
                hass, password)
            if user is None:
                return False

            request[KEY_HASS_USER] = user
            _LOGGER.info(
                'Basic auth with api_password is going to deprecate,'
                ' please use a bearer token to access %s from %s',
                request.path, request[KEY_REAL_IP])
            old_auth_warning.add(request.path)
            return True

        return False

    async def async_validate_signed_request(request):
        """Validate a signed request."""
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

        request[KEY_HASS_USER] = refresh_token.user
        return True

    async def async_validate_trusted_networks(request):
        """Test if request is from a trusted ip."""
        ip_addr = request[KEY_REAL_IP]

        if not any(ip_addr in trusted_network
                   for trusted_network in trusted_networks):
            return False

        user = await hass.auth.async_get_owner()
        if user is None:
            return False

        request[KEY_HASS_USER] = user
        return True

    async def async_validate_legacy_api_password(request, password):
        """Validate api_password."""
        user = await legacy_api_password.async_validate_password(
            hass, password)
        if user is None:
            return False

        request[KEY_HASS_USER] = user
        return True

    @middleware
    async def auth_middleware(request, handler):
        """Authenticate as middleware."""
        authenticated = False

        if (HTTP_HEADER_HA_AUTH in request.headers or
                DATA_API_PASSWORD in request.query):
            if request.path not in old_auth_warning:
                _LOGGER.log(
                    logging.INFO if support_legacy else logging.WARNING,
                    'api_password is going to deprecate. You need to use a'
                    ' bearer token to access %s from %s',
                    request.path, request[KEY_REAL_IP])
                old_auth_warning.add(request.path)

        if (hdrs.AUTHORIZATION in request.headers and
                await async_validate_auth_header(request)):
            # it included both use_auth and api_password Basic auth
            authenticated = True

        # We first start with a string check to avoid parsing query params
        # for every request.
        elif (request.method == "GET" and SIGN_QUERY_PARAM in request.query and
              await async_validate_signed_request(request)):
            authenticated = True

        elif (trusted_networks and
              await async_validate_trusted_networks(request)):
            authenticated = True

        elif (support_legacy and HTTP_HEADER_HA_AUTH in request.headers and
              await async_validate_legacy_api_password(
                  request, request.headers[HTTP_HEADER_HA_AUTH])):
            authenticated = True

        elif (support_legacy and DATA_API_PASSWORD in request.query and
              await async_validate_legacy_api_password(
                  request, request.query[DATA_API_PASSWORD])):
            authenticated = True

        request[KEY_AUTHENTICATED] = authenticated
        return await handler(request)

    app.middlewares.append(auth_middleware)
