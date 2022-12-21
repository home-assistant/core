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
have type FlowResultType.CREATE_ENTRY and "result" key will contain an authorization code.
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
from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus
from ipaddress import ip_address
from typing import TYPE_CHECKING, Any

from aiohttp import web
import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.auth import AuthManagerFlowManager
from homeassistant.auth.models import Credentials
from homeassistant.components import onboarding
from homeassistant.components.http.auth import async_user_not_allowed_do_auth
from homeassistant.components.http.ban import (
    log_invalid_auth,
    process_success_login,
    process_wrong_login,
)
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant

from . import indieauth

if TYPE_CHECKING:
    from . import StoreResultType


async def async_setup(
    hass: HomeAssistant, store_result: Callable[[str, Credentials], str]
) -> None:
    """Component to allow users to login."""
    hass.http.register_view(WellKnownOAuthInfoView)
    hass.http.register_view(AuthProvidersView)
    hass.http.register_view(LoginFlowIndexView(hass.auth.login_flow, store_result))
    hass.http.register_view(LoginFlowResourceView(hass.auth.login_flow, store_result))


class WellKnownOAuthInfoView(HomeAssistantView):
    """View to host the OAuth2 information."""

    requires_auth = False
    url = "/.well-known/oauth-authorization-server"
    name = "well-known/oauth-authorization-server"

    async def get(self, request: web.Request) -> web.Response:
        """Return the well known OAuth2 authorization info."""
        return self.json(
            {
                "authorization_endpoint": "/auth/authorize",
                "token_endpoint": "/auth/token",
                "revocation_endpoint": "/auth/revoke",
                "response_types_supported": ["code"],
                "service_documentation": "https://developers.home-assistant.io/docs/auth_api",
            }
        )


class AuthProvidersView(HomeAssistantView):
    """View to get available auth providers."""

    url = "/auth/providers"
    name = "api:auth:providers"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Get available auth providers."""
        hass: HomeAssistant = request.app["hass"]
        if not onboarding.async_is_user_onboarded(hass):
            return self.json_message(
                message="Onboarding not finished",
                status_code=HTTPStatus.BAD_REQUEST,
                message_code="onboarding_required",
            )

        return self.json(
            [
                {"name": provider.name, "id": provider.id, "type": provider.type}
                for provider in hass.auth.auth_providers
            ]
        )


def _prepare_result_json(
    result: data_entry_flow.FlowResult,
) -> data_entry_flow.FlowResult:
    """Convert result to JSON."""
    if result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY:
        data = result.copy()
        data.pop("result")
        data.pop("data")
        return data

    if result["type"] != data_entry_flow.FlowResultType.FORM:
        return result

    data = result.copy()

    if (schema := data["data_schema"]) is None:
        data["data_schema"] = []
    else:
        data["data_schema"] = voluptuous_serialize.convert(schema)

    return data


class LoginFlowBaseView(HomeAssistantView):
    """Base class for the login views."""

    requires_auth = False

    def __init__(
        self,
        flow_mgr: AuthManagerFlowManager,
        store_result: StoreResultType,
    ) -> None:
        """Initialize the flow manager index view."""
        self._flow_mgr = flow_mgr
        self._store_result = store_result

    async def _async_flow_result_to_response(
        self,
        request: web.Request,
        client_id: str,
        result: data_entry_flow.FlowResult,
    ) -> web.Response:
        """Convert the flow result to a response."""
        if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
            # @log_invalid_auth does not work here since it returns HTTP 200.
            # We need to manually log failed login attempts.
            if (
                result["type"] == data_entry_flow.FlowResultType.FORM
                and (errors := result.get("errors"))
                and errors.get("base")
                in (
                    "invalid_auth",
                    "invalid_code",
                )
            ):
                await process_wrong_login(request)
            return self.json(_prepare_result_json(result))

        hass: HomeAssistant = request.app["hass"]

        if not await indieauth.verify_redirect_uri(
            hass, client_id, result["context"]["redirect_uri"]
        ):
            return self.json_message("Invalid redirect URI", HTTPStatus.FORBIDDEN)

        result.pop("data")
        result.pop("context")

        result_obj: Credentials = result.pop("result")

        # Result can be None if credential was never linked to a user before.
        user = await hass.auth.async_get_user_by_credentials(result_obj)

        if user is not None and (
            user_access_error := async_user_not_allowed_do_auth(hass, user)
        ):
            return self.json_message(
                f"Login blocked: {user_access_error}", HTTPStatus.FORBIDDEN
            )

        await process_success_login(request)
        result["result"] = self._store_result(client_id, result_obj)

        return self.json(result)


class LoginFlowIndexView(LoginFlowBaseView):
    """View to create a login flow."""

    url = "/auth/login_flow"
    name = "api:auth:login_flow"

    async def get(self, request: web.Request) -> web.Response:
        """Do not allow index of flows in progress."""
        return web.Response(status=HTTPStatus.METHOD_NOT_ALLOWED)

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
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Create a new login flow."""
        client_id: str = data["client_id"]
        redirect_uri: str = data["redirect_uri"]

        if not indieauth.verify_client_id(client_id):
            return self.json_message("Invalid client id", HTTPStatus.BAD_REQUEST)

        handler: tuple[str, ...] | str
        if isinstance(data["handler"], list):
            handler = tuple(data["handler"])
        else:
            handler = data["handler"]

        try:
            result = await self._flow_mgr.async_init(
                handler,  # type: ignore[arg-type]
                context={
                    "ip_address": ip_address(request.remote),  # type: ignore[arg-type]
                    "credential_only": data.get("type") == "link_user",
                    "redirect_uri": redirect_uri,
                },
            )
        except data_entry_flow.UnknownHandler:
            return self.json_message("Invalid handler specified", HTTPStatus.NOT_FOUND)
        except data_entry_flow.UnknownStep:
            return self.json_message(
                "Handler does not support init", HTTPStatus.BAD_REQUEST
            )

        return await self._async_flow_result_to_response(request, client_id, result)


class LoginFlowResourceView(LoginFlowBaseView):
    """View to interact with the flow manager."""

    url = "/auth/login_flow/{flow_id}"
    name = "api:auth:login_flow:resource"

    async def get(self, request: web.Request) -> web.Response:
        """Do not allow getting status of a flow in progress."""
        return self.json_message("Invalid flow specified", HTTPStatus.NOT_FOUND)

    @RequestDataValidator(
        vol.Schema(
            {vol.Required("client_id"): str},
            extra=vol.ALLOW_EXTRA,
        )
    )
    @log_invalid_auth
    async def post(
        self, request: web.Request, data: dict[str, Any], flow_id: str
    ) -> web.Response:
        """Handle progressing a login flow request."""
        client_id: str = data.pop("client_id")

        if not indieauth.verify_client_id(client_id):
            return self.json_message("Invalid client id", HTTPStatus.BAD_REQUEST)

        try:
            # do not allow change ip during login flow
            flow = self._flow_mgr.async_get(flow_id)
            if flow["context"]["ip_address"] != ip_address(request.remote):  # type: ignore[arg-type]
                return self.json_message("IP address changed", HTTPStatus.BAD_REQUEST)
            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTPStatus.NOT_FOUND)
        except vol.Invalid:
            return self.json_message("User input malformed", HTTPStatus.BAD_REQUEST)

        return await self._async_flow_result_to_response(request, client_id, result)

    async def delete(self, request: web.Request, flow_id: str) -> web.Response:
        """Cancel a flow in progress."""
        try:
            self._flow_mgr.async_abort(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message("Invalid flow specified", HTTPStatus.NOT_FOUND)

        return self.json_message("Flow aborted")
