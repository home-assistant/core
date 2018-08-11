"""HTTP views handle login flow.

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

Pass in parameter 'client_id' and 'redirect_url' validate by indieauth.

Pass in parameter 'handler' to specify the auth provider to use. Auth providers
are identified by type and id.

{
    "client_id": "https://hassbian.local:8123/",
    "handler": ["local_provider", null],
    "redirect_url": "https://hassbian.local:8123/"
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
"""
import aiohttp.web
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.http.ban import process_wrong_login, \
    log_invalid_auth
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView, FlowManagerResourceView)
from . import indieauth


async def async_setup(hass, store_credentials):
    """Component to allow users to login."""
    hass.http.register_view(AuthProvidersView)
    hass.http.register_view(LoginFlowIndexView(hass.auth.login_flow))
    hass.http.register_view(
        LoginFlowResourceView(hass.auth.login_flow, store_credentials))


class AuthProvidersView(HomeAssistantView):
    """View to get available auth providers."""

    url = '/auth/providers'
    name = 'api:auth:providers'
    requires_auth = False

    async def get(self, request):
        """Get available auth providers."""
        return self.json([{
            'name': provider.name,
            'id': provider.id,
            'type': provider.type,
        } for provider in request.app['hass'].auth.auth_providers])


class LoginFlowIndexView(FlowManagerIndexView):
    """View to create a config flow."""

    url = '/auth/login_flow'
    name = 'api:auth:login_flow'
    requires_auth = False

    async def get(self, request):
        """Do not allow index of flows in progress."""
        return aiohttp.web.Response(status=405)

    @RequestDataValidator(vol.Schema({
        vol.Required('client_id'): str,
        vol.Required('handler'): vol.Any(str, list),
        vol.Required('redirect_uri'): str,
    }))
    @log_invalid_auth
    async def post(self, request, data):
        """Create a new login flow."""
        if not indieauth.verify_redirect_uri(data['client_id'],
                                             data['redirect_uri']):
            return self.json_message('invalid client id or redirect uri', 400)

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

    async def get(self, request, flow_id):
        """Do not allow getting status of a flow in progress."""
        return self.json_message('Invalid flow specified', 404)

    @RequestDataValidator(vol.Schema({
        'client_id': str
    }, extra=vol.ALLOW_EXTRA))
    @log_invalid_auth
    async def post(self, request, flow_id, data):
        """Handle progressing a login flow request."""
        client_id = data.pop('client_id')

        if not indieauth.verify_client_id(client_id):
            return self.json_message('Invalid client id', 400)

        try:
            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)
        except vol.Invalid:
            return self.json_message('User input malformed', 400)

        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            # @log_invalid_auth does not work here since it returns HTTP 200
            # need manually log failed login attempts
            if result['errors'] is not None and \
                    result['errors'].get('base') == 'invalid_auth':
                await process_wrong_login(request)
            return self.json(self._prepare_result_json(result))

        result.pop('data')
        result['result'] = self._store_credentials(client_id, result['result'])

        return self.json(result)
