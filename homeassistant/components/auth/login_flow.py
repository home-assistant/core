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

And optional parameter 'type' has to set as 'link_user' if login flow used for
link credential to exist user. Default 'type' is 'authorize'.

{
    "client_id": "https://hassbian.local:8123/",
    "handler": ["local_provider", null],
    "redirect_url": "https://hassbian.local:8123/",
    "type': "authorize"
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
The authorization code associated with an authorized user by default, it will
associate with an credential if "type" set to "link_user" in
"/auth/login_flow"

{
    "flow_id": "8f7e42faab604bcab7ac43c44ca34d58",
    "handler": ["insecure_example", null],
    "result": "411ee2f916e648d691e937ae9344681e",
    "title": "Example",
    "type": "create_entry",
    "version": 1
}
"""
from ipaddress import ip_address

from aiohttp import web
import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.components.http.ban import (
    log_invalid_auth,
    process_success_login,
    process_wrong_login,
)
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import (
    HTTP_BAD_REQUEST,
    HTTP_METHOD_NOT_ALLOWED,
    HTTP_NOT_FOUND,
)

from . import indieauth


async def async_setup(hass, store_result):
    """Component to allow users to login."""
    hass.http.register_view(AuthProvidersView)
    hass.http.register_view(LoginFlowIndexView(hass.auth.login_flow, store_result))
    hass.http.register_view(LoginFlowResourceView(hass.auth.login_flow, store_result))


class AuthProvidersView(HomeAssistantView):
    """View to get available auth providers."""

    url = "/auth/providers"
    name = "api:auth:providers"
    requires_auth = False

    async def get(self, request):
        """Get available auth providers."""
        hass = request.app["hass"]
        if not hass.components.onboarding.async_is_user_onboarded():
            return self.json_message(
                message="Onboarding not finished",
                status_code=HTTP_BAD_REQUEST,
                message_code="onboarding_required",
            )

        return self.json(
            [
                {"name": provider.name, "id": provider.id, "type": provider.type}
                for provider in hass.auth.auth_providers
            ]
        )


def _prepare_result_json(result):
    """Convert result to JSON."""
    if result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
        data = result.copy()
        data.pop("result")
        data.pop("data")
        return data

    if result["type"] != data_entry_flow.RESULT_TYPE_FORM:
        return result

    data = result.copy()

    schema = data["data_schema"]
    if schema is None:
        data["data_schema"] = []
    else:
        data["data_schema"] = voluptuous_serialize.convert(schema)

    return data


class LoginFlowIndexView(HomeAssistantView):
    """View to create a config flow."""

    url = "/auth/login_flow"
    name = "api:auth:login_flow"
    requires_auth = False

    def __init__(self, flow_mgr, store_result):
        """Initialize the flow manager index view."""
        self._flow_mgr = flow_mgr
        self._store_result = store_result

    async def get(self, request):
        """Do not allow index of flows in progress."""
        return web.Response(status=HTTP_METHOD_NOT_ALLOWED)

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("client_id"): str,
                vol.Required("handler"): vol.Any(str, list),
                vol.Required("redirect_uri"): str,
                vol.Optional("type", default="authorize"): str,
            }
        )
    )
    @log_invalid_auth
    async def post(self, request, data):
        """Create a new login flow."""
        if not await indieauth.verify_redirect_uri(
            request.app["hass"], data["client_id"], data["redirect_uri"]
        ):
            return self.json_message(
                "invalid client id or redirect uri", HTTP_BAD_REQUEST
            )

        if isinstance(data["handler"], list):
            handler = tuple(data["handler"])
        else:
            handler = data["handler"]

        try:
            result = await self._flow_mgr.async_init(
                handler,
                context={
                    "ip_address": ip_address(request.remote),
                    "credential_only": data.get("type") == "link_user",
                },
            )
        except data_entry_flow.UnknownHandler:
            return self.json_message("Invalid handler specified", HTTP_NOT_FOUND)
        except data_entry_flow.UnknownStep:
            return self.json_message("Handler does not support init", HTTP_BAD_REQUEST)

        if result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            await process_success_login(request)
            result.pop("data")
            result["result"] = self._store_result(data["client_id"], result["result"])
            return self.json(result)

        return self.json(_prepare_result_json(result))


class LoginFlowResourceView(HomeAssistantView):
    """View to interact with the flow manager."""

    url = "/auth/login_flow/{flow_id}"
    name = "api:auth:login_flow:resource"
    requires_auth = False

    def __init__(self, flow_mgr, store_result):
        """Initialize the login flow resource view."""
        self._flow_mgr = flow_mgr
        self._store_result = store_result

    async def get(self, request):
        """Do not allow getting status of a flow in progress."""
        return self.json_message("Invalid flow specified", HTTP_NOT_FOUND)

    @RequestDataValidator(vol.Schema({"client_id": str}, extra=vol.ALLOW_EXTRA))
    @log_invalid_auth
    async def post(self, request, flow_id, data):
        """Handle progressing a login flow request."""
        client_id = data.pop("client_id")

        if not indieauth.verify_client_id(client_id):
            return self.json_message("Invalid client id", HTTP_BAD_REQUEST)

        try:
            # do not allow change ip during login flow
            for flow in self._flow_mgr.async_progress():
                if flow["flow_id"] == flow_id and flow["context"][
                    "ip_address"
                ] != ip_address(request.remote):
                    return self.json_message("IP address changed", HTTP_BAD_REQUEST)

            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTP_NOT_FOUND)
        except vol.Invalid:
            return self.json_message("User input malformed", HTTP_BAD_REQUEST)

        if result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            # @log_invalid_auth does not work here since it returns HTTP 200
            # need manually log failed login attempts
            if result.get("errors") is not None and result["errors"].get("base") in [
                "invalid_auth",
                "invalid_code",
            ]:
                await process_wrong_login(request)
            return self.json(_prepare_result_json(result))

        result.pop("data")
        result["result"] = self._store_result(client_id, result["result"])

        return self.json(result)

    async def delete(self, request, flow_id):
        """Cancel a flow in progress."""
        try:
            self._flow_mgr.async_abort(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTP_NOT_FOUND)

        return self.json_message("Flow aborted")
