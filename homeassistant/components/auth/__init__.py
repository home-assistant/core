"""Component to allow users to login and get tokens.

All requests will require passing in a valid client ID and secret via HTTP
Basic Auth.

# GET /auth/providers

Return a list of auth providers. Example:

[
    {
        "name": "Local",
        "id": null,
        "type": "local_provider",
    }
]

# POST /auth/login_flow

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

# POST /auth/login_flow/{flow_id}

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

# POST /auth/token

This is an OAuth2 endpoint for granting tokens. We currently support the grant
types "authorization_code" and "refresh_token". Because we follow the OAuth2
spec, data should be send in formatted as x-www-form-urlencoded. Examples will
be in JSON as it's more readable.

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

DOMAIN = 'auth'
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

    url = '/auth/providers'
    name = 'api:auth:providers'
    requires_auth = False

    @verify_client
    async def get(self, request, client):
        """Get available auth providers."""
        return self.json([{
            'name': provider.name,
            'id': provider.id,
            'type': provider.type,
        } for provider in request.app['hass'].auth.async_auth_providers])


class LoginFlowIndexView(FlowManagerIndexView):
    """View to create a config flow."""

    url = '/auth/login_flow'
    name = 'api:auth:login_flow'
    requires_auth = False

    async def get(self, request):
        """Do not allow index of flows in progress."""
        return aiohttp.web.Response(status=405)

    # pylint: disable=arguments-differ
    @verify_client
    @RequestDataValidator(vol.Schema({
        vol.Required('handler'): vol.Any(str, list),
        vol.Required('redirect_uri'): str,
    }))
    async def post(self, request, client, data):
        """Create a new login flow."""
        if data['redirect_uri'] not in client.redirect_uris:
            return self.json_message('invalid redirect uri', )

        # pylint: disable=no-value-for-parameter
        return await super().post(request)


class LoginFlowResourceView(FlowManagerResourceView):
    """View to interact with the flow manager."""

    url = '/auth/login_flow/{flow_id}'
    name = 'api:auth:login_flow:resource'
    requires_auth = False

    def __init__(self, flow_mgr, store_credentials):
        """Initialize the login flow resource view."""
        super().__init__(flow_mgr)
        self._store_credentials = store_credentials

    # pylint: disable=arguments-differ
    async def get(self, request):
        """Do not allow getting status of a flow in progress."""
        return self.json_message('Invalid flow specified', 404)

    # pylint: disable=arguments-differ
    @verify_client
    @RequestDataValidator(vol.Schema(dict), allow_empty=True)
    async def post(self, request, client, flow_id, data):
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
        result['result'] = self._store_credentials(client.id, result['result'])

        return self.json(result)


class GrantTokenView(HomeAssistantView):
    """View to grant tokens."""

    url = '/auth/token'
    name = 'api:auth:token'
    requires_auth = False

    def __init__(self, retrieve_credentials):
        """Initialize the grant token view."""
        self._retrieve_credentials = retrieve_credentials

    @verify_client
    async def post(self, request, client):
        """Grant a token."""
        hass = request.app['hass']
        data = await request.post()
        grant_type = data.get('grant_type')

        if grant_type == 'authorization_code':
            return await self._async_handle_auth_code(
                hass, client.id, data)

        elif grant_type == 'refresh_token':
            return await self._async_handle_refresh_token(
                hass, client.id, data)

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

        user = await hass.auth.async_get_or_create_user(credentials)
        refresh_token = await hass.auth.async_create_refresh_token(user,
                                                                   client_id)
        access_token = hass.auth.async_create_access_token(refresh_token)

        return self.json({
            'access_token': access_token.token,
            'token_type': 'Bearer',
            'refresh_token': refresh_token.token,
            'expires_in':
                int(refresh_token.access_token_expiration.total_seconds()),
        })

    async def _async_handle_refresh_token(self, hass, client_id, data):
        """Handle authorization code request."""
        token = data.get('refresh_token')

        if token is None:
            return self.json({
                'error': 'invalid_request',
            }, status_code=400)

        refresh_token = await hass.auth.async_get_refresh_token(token)

        if refresh_token is None or refresh_token.client_id != client_id:
            return self.json({
                'error': 'invalid_grant',
            }, status_code=400)

        access_token = hass.auth.async_create_access_token(refresh_token)

        return self.json({
            'access_token': access_token.token,
            'token_type': 'Bearer',
            'expires_in':
                int(refresh_token.access_token_expiration.total_seconds()),
        })


class LinkUserView(HomeAssistantView):
    """View to link existing users to new credentials."""

    url = '/auth/link_user'
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
