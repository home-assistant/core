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
import logging
import uuid

import aiohttp.web
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.core import callback
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView, FlowManagerResourceView)
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator

from .client import verify_client
from . import token

DOMAIN = 'auth'
REQUIREMENTS = ['pyjwt==1.6.1']
DEPENDENCIES = ['http']
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Component to allow users to login."""
    store_credentials, retrieve_credentials = _create_cred_store()

    hass.http.register_view(AuthProvidersView)
    hass.http.register_view(LoginFlowIndexView(hass.auth.login_flow))
    hass.http.register_view(
        LoginFlowResourceView(hass.auth.login_flow, store_credentials))
    hass.http.register_view(GrantTokenView(retrieve_credentials))
    hass.http.register_view(LinkUserView(retrieve_credentials))

    return True


class AuthProvidersView(HomeAssistantView):
    """View to get available auth providers."""

    url = '/api/auth/providers'
    name = 'api:auth:providers'
    requires_auth = False

    @verify_client
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

    @verify_client
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

    @verify_client
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

    @verify_client
    async def post(self, request, client_id):
        """Grant a token."""
        hass = request.app['hass']
        data = await request.post()
        grant_type = data.get('grant_type')

        secret = hass.data.get(token.DATA_SECRET)
        if secret is None:
            secret = await hass.async_add_job(
                token.load_or_create_secret, hass)

        if grant_type == 'authorization_code':
            return await self._async_handle_auth_code(
                hass, secret, client_id, data)

        elif grant_type == 'refresh_token':
            return await self._async_handle_refresh_token(
                hass, secret, client_id, data)

        return self.json({
            'error': 'unsupported_grant_type',
        }, status_code=400)

    async def _async_handle_auth_code(self, hass, secret, client_id, data):
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

        user = await hass.auth.async_get_or_create_user(credentials)
        user_token = await user.async_create_token(client_id)
        refresh_token = token.async_refresh_token(hass, secret, user_token)
        access_token = token.async_access_token(hass, secret, user_token)

        return self.json({
            'access_token': access_token,
            'token_type': 'Bearer',
            'refresh_token': refresh_token,
            'expires_in': int(user_token.access_token_valid.total_seconds()),
        })

    async def _async_handle_refresh_token(self, hass, secret, client_id, data):
        """Handle authorization code request."""
        refresh_token = data.get('refresh_token')

        if refresh_token is None:
            return self.json({
                'error': 'invalid_request',
            }, status_code=400)

        info = await token.async_resolve_token(
            hass, secret, refresh_token, client_id)

        if info is None:
            return self.json({
                'error': 'invalid_grant',
            }, status_code=400)

        access_token = token.async_access_token(hass, secret, info['token'])

        return self.json({
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': int(
                info['token'].access_token_valid.total_seconds()),
        })


class LinkUserView(HomeAssistantView):
    """View to link existing users to new credentials."""

    url = '/api/auth/link_user'
    name = 'api:auth:link_user'

    def __init__(self, retrieve_credentials):
        """Initialize the link user view."""
        self._retrieve_credentials = retrieve_credentials

    @RequestDataValidator(vol.Schema({
        'code': str,
        'client_id': str,
    }))
    async def post(self, request, data):
        """Link a user."""
        hass = request.app['hass']
        user = request['hass_user']

        credentials = self._retrieve_credentials(
            data['client_id'], data['code'])

        if credentials is None:
            return self.json_message('Invalid code', status_code=400)

        await hass.auth.async_link_user(user, credentials)
        return self.json_message('User linked')


@callback
def _create_cred_store():
    """Create a credential store."""
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

    return store_credentials, retrieve_credentials
