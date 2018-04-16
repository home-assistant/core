"""Component to allow users to login and get tokens.

All requests will require passing in a valid client ID and secret via HTTP
Basic Auth.

# GET /api/auth/providers

Return a list of auth providers. Example:

[
    {
        "name": "Local",
        "id": null,
        "type": "local_provider",
    }
]

# POST /api/auth/login_flow

Create a login flow. Will return the first step of the flow.

Pass in parameter 'handler' to specify the auth provider to use. Auth providers
are identified by type and id.

{
    "handler": ["local_provider", null]
}

Return value will be a step in a data entry flow. See the docs for data entry
flow for details.

{
    "data_schema": [
        {"name": "username", "type": "string"},
        {"name": "password", "type": "string"}
    ],
    "errors": {},
    "flow_id": "8f7e42faab604bcab7ac43c44ca34d58",
    "handler": ["insecure_example", null],
    "step_id": "init",
    "type": "form"
}

# POST /api/auth/login_flow/{flow_id}

Progress the flow. Most flows will be 1 page, but could optionally add extra
login challenges, like TFA. Once the flow has finished, the returned step will
have type "create_entry" and "result" key will contain an authorization code.

{
    "flow_id": "8f7e42faab604bcab7ac43c44ca34d58",
    "handler": ["insecure_example", null],
    "result": "411ee2f916e648d691e937ae9344681e",
    "source": "user",
    "title": "Example",
    "type": "create_entry",
    "version": 1
}

# POST /api/auth/token

This is an OAuth2 endpoint for granting tokens. We currently support the grant
types "authorization_code" and "refresh_token".

## Grant type authorization_code

Exchange the authorization code retrieved from the login flow for tokens.

{
    "grant_type": "authorization_code",
    "code": "411ee2f916e648d691e937ae9344681e"
}

Return value will be the access and refresh tokens. The access token will have
a limited expiration. New access tokens can be requested using the refresh
token.

{
    "access_token": "ABCDEFGH",
    "expires_in": 1800,
    "refresh_token": "IJKLMNOPQRST",
    "token_type": "Bearer"
}

## Grant type refresh_token

Request a new access token using a refresh token.

{
    "grant_type": "refresh_token",
    "refresh_token": "IJKLMNOPQRST"
}

Return value will be a new access token. The access token will have
a limited expiration.

{
    "access_token": "ABCDEFGH",
    "expires_in": 1800,
    "token_type": "Bearer"
}
"""
import base64
from datetime import timedelta
from functools import wraps
import hmac
import logging
import uuid

import aiohttp.hdrs
import aiohttp.web
import voluptuous as vol

from homeassistant import auth, data_entry_flow
from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView, FlowManagerResourceView)
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.util import dt as dt_util

DOMAIN = 'auth'
REQUIREMENTS = ['pyjwt==1.6.1']
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)

TEMP_SECRET = 'supersecret'
ACCESS_TOKEN_EXPIRATION = timedelta(minutes=30)


async def async_setup(hass, config):
    """Component to allow users to login."""

    temp_credentials = {}

    @callback
    def store_credentials(client_id, credentials):
        """Store credentials and return a code to retrieve it."""
        code = uuid.uuid4().hex
        temp_credentials[(client_id, code)] = credentials
        return code

    @callback
    def retrieve_credentials(client_id, code):
        """Retrieve credentials."""
        return temp_credentials.pop((client_id, code), None)

    hass.http.register_view(AuthProvidersView)
    hass.http.register_view(LoginFlowIndexView(hass.auth.login_flow))
    hass.http.register_view(
        LoginFlowResourceView(hass.auth.login_flow, store_credentials))
    hass.http.register_view(GrantTokenView(retrieve_credentials))

    return True


@callback
def verify_client(request):
    """Decorator to verify the client id/secret in a time safe manner."""
    return 'fake-client-id'  # TEMP

    # Verify client_id, secret
    if aiohttp.hdrs.AUTHORIZATION not in request.headers:
        return False

    auth_type, auth_value = \
        request.headers.get(aiohttp.hdrs.AUTHORIZATION).split(' ', 1)

    if auth_type != 'Basic':
        return False

    # decoded = base64.b64decode(auth_value).decode('utf-8')
    # client_id, client_secret = decoded.split(':', 1)
    # hass = request.app['hass']
    # Use hmac.compare_digest(client_secret, client.secret)

    # Look up client id, compare client secret.
    # secure_lookup should always run in same time wheter it finds or not
    # finds a matching client.
    # client = hass.auth.async_secure_lookup_client(client_id)
    # if we don't find a client, we should still compare passed client
    # secret to itself to spend the same amount of time as a correct
    # request.


def VerifyClient(method):
    """Decorator to verify client id/secret on requests."""
    @wraps(method)
    async def wrapper(view, request, *args, **kwargs):
        """Verify client id/secret before doing request."""
        client_id = verify_client(request)

        if client_id is None:
            return view.json({
                'error': 'invalid_client',
            }, status_code=401)

        return await method(
            view, request, *args, client_id=client_id, **kwargs)

    return wrapper


class AuthProvidersView(HomeAssistantView):
    """View to get available auth providers."""

    url = '/api/auth/providers'
    name = 'api:auth:providers'
    requires_auth = False

    @VerifyClient
    async def get(self, request, client_id):
        """Get available auth providers."""
        return self.json(request.app['hass'].auth.async_auth_providers())


class LoginFlowIndexView(FlowManagerIndexView):
    """View to create config flows."""

    url = '/api/auth/login_flow'
    name = 'api:auth:login_flow'
    requires_auth = False

    async def get(self, request):
        """Do not allow index of flows in progress."""
        return aiohttp.web.Response(status=405)

    @VerifyClient
    async def post(self, request, client_id):
        """Create a new login flow."""
        return await super().post(request)


class LoginFlowResourceView(FlowManagerResourceView):
    """View to interact with the flow manager."""

    url = '/api/auth/login_flow/{flow_id}'
    name = 'api:auth:login_flow:resource'
    requires_auth = False

    def __init__(self, flow_mgr, store_credentials):
        """Initialize the login flow resource view."""
        super().__init__(flow_mgr)
        self._store_credentials = store_credentials

    async def get(self, request):
        """Do not allow getting status of a flow in progress."""
        return self.json_message('Invalid flow specified', 404)

    @VerifyClient
    @RequestDataValidator(vol.Schema(dict), allow_empty=True)
    async def post(self, request, client_id, flow_id, data):
        """Handle progressing a login flow request."""
        try:
            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)
        except vol.Invalid:
            return self.json_message('User input malformed', 400)

        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return self.json(self._prepare_result_json(result))

        result.pop('data')
        result['result'] = self._store_credentials(client_id, result['result'])

        return self.json(result)


class GrantTokenView(HomeAssistantView):
    """View to grant tokens."""

    url = '/api/auth/token'
    name = 'api:auth:token'
    requires_auth = False

    def __init__(self, retrieve_credentials):
        """Initialize the grant token view."""
        self._retrieve_credentials = retrieve_credentials

    @VerifyClient
    async def post(self, request, client_id):
        """Grant a token."""
        hass = request.app['hass']
        data = await request.post()
        grant_type = data.get('grant_type')

        if grant_type == 'authorization_code':
            return await self._async_handle_auth_code(hass, client_id, data)

        elif grant_type == 'refresh_token':
            return self._async_handle_refresh_token(hass, client_id, data)

        return self.json({
            'error': 'unsupported_grant_type',
        }, status_code=400)

    async def _async_handle_auth_code(self, hass, client_id, data):
        """Handle authorization code request."""
        code = data.get('code')

        if code is None:
            return self.json({
                'error': 'invalid_request',
            }, status_code=400)

        credentials = self._retrieve_credentials(client_id, code)

        if credentials is None:
            return self.json({
                'error': 'invalid_request',
            }, status_code=400)

        # TODO if we make this request authenticated, link the user

        user = await hass.auth.async_get_or_create_user(credentials)
        refresh_token = async_refresh_token(hass, client_id, user)
        access_token = async_access_token(hass, client_id, refresh_token)

        return self.json({
            'access_token': access_token,
            'token_type': 'Bearer',
            'refresh_token': refresh_token,
            'expires_in': int(ACCESS_TOKEN_EXPIRATION.total_seconds()),
        })

    @callback
    def _async_handle_refresh_token(self, hass, client_id, data):
        """Handle authorization code request."""
        import jwt

        refresh_token = data.get('refresh_token')

        if refresh_token is None:
            return self.json({
                'error': 'invalid_request',
            }, status_code=400)

        try:
            access_token = async_access_token(hass, client_id, refresh_token)
        except jwt.exceptions.InvalidTokenError:
            # If the refresh token is invalid.
            return self.json({
                'error': 'invalid_grant',
            }, status_code=400)

        return self.json({
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': int(ACCESS_TOKEN_EXPIRATION.total_seconds()),
        })


@callback
def async_refresh_token(hass, client_id, user):
    """Generate a set of tokens for a user.

    typ: token type, refresh.
    sub: identifier of the user.
    aud: id of client requesting token on behalf of user.
    iat: unix timestamp when token was issued.
    """
    import jwt

    return jwt.encode({
        'typ': 'refresh',
        'sub': user.id,
        'aud': client_id,
        'iat': dt_util.utcnow()
    }, TEMP_SECRET, algorithm='HS256').decode('utf-8')


@callback
def async_access_token(hass, client_id, refresh_token):
    """Generate an access token for a user.

    typ: token type, access.
    sub: identifier of the user.
    aud: id of client requesting token on behalf of user.
    auth_time: unix timestamp the refresh token was granted.
    iat: unix timestsamp when token was issued.
    exp: unix timestamp when token expires.
    """
    import jwt

    claims = jwt.decode(
        refresh_token.encode('utf-8'), TEMP_SECRET, algorithms=['HS256'],
        audience=client_id)

    return jwt.encode({
        'typ': 'access',
        'sub': claims['sub'],
        'aud': claims['aud'],
        'auth_time': claims['iat'],
        'iat': dt_util.utcnow(),
        'exp': dt_util.utcnow() + ACCESS_TOKEN_EXPIRATION
    }, TEMP_SECRET, algorithm='HS256').decode('utf-8')


@bind_hass
async def async_valid_access_token(hass, access_token, client_id=None):
    """Validate an access token."""
    return (await async_get_claims(hass, access_token, client_id)) is not None


async def async_get_claims(hass, token, client_id=None):
    """Get claims from a token.

    Return None if token cannot be validated."""
    import jwt

    options = {}
    if client_id is None:
        options['verify_aud'] = False

    try:
        claims = jwt.decode(token, TEMP_SECRET, audience=client_id,
                            options=options)
    except jwt.exceptions.InvalidTokenError:
        return None

    # Fetch the user and see if user.token_min_issued
    user = await hass.auth.async_get_user(claims['sub'])

    if user is None or not user.is_active:
        return None

    # Make sure the token has not been issued before the minimum time.
    # This feature allows a user to instant invalidate all old tokens.
    if claims['auth_time'] < int(user.token_min_issued.timestamp()):
        return None

    return claims
