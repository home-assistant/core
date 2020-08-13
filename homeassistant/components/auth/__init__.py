"""Component to allow users to login and get tokens.

# POST /auth/token

This is an OAuth2 endpoint for granting tokens. We currently support the grant
types "authorization_code" and "refresh_token". Because we follow the OAuth2
spec, data should be send in formatted as x-www-form-urlencoded. Examples will
be in JSON as it's more readable.

## Grant type authorization_code

Exchange the authorization code retrieved from the login flow for tokens.

{
    "client_id": "https://hassbian.local:8123/",
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
    "client_id": "https://hassbian.local:8123/",
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

## Revoking a refresh token

It is also possible to revoke a refresh token and all access tokens that have
ever been granted by that refresh token. Response code will ALWAYS be 200.

{
    "token": "IJKLMNOPQRST",
    "action": "revoke"
}

# Websocket API

## Get current user

Send websocket command `auth/current_user` will return current user of the
active websocket connection.

{
    "id": 10,
    "type": "auth/current_user",
}

The result payload likes

{
    "id": 10,
    "type": "result",
    "success": true,
    "result": {
        "id": "USER_ID",
        "name": "John Doe",
        "is_owner": true,
        "credentials": [{
            "auth_provider_type": "homeassistant",
            "auth_provider_id": null
        }],
        "mfa_modules": [{
            "id": "totp",
            "name": "TOTP",
            "enabled": true
        }]
    }
}

## Create a long-lived access token

Send websocket command `auth/long_lived_access_token` will create
a long-lived access token for current user. Access token will not be saved in
Home Assistant. User need to record the token in secure place.

{
    "id": 11,
    "type": "auth/long_lived_access_token",
    "client_name": "GPS Logger",
    "lifespan": 365
}

Result will be a long-lived access token:

{
    "id": 11,
    "type": "result",
    "success": true,
    "result": "ABCDEFGH"
}

"""
from datetime import timedelta
import logging
import uuid

from aiohttp import web
import voluptuous as vol

from homeassistant.auth.models import (
    TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    Credentials,
    User,
)
from homeassistant.components import websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.http.ban import log_invalid_auth
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import HTTP_BAD_REQUEST, HTTP_FORBIDDEN, HTTP_OK
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

from . import indieauth, login_flow, mfa_setup_flow

DOMAIN = "auth"
WS_TYPE_CURRENT_USER = "auth/current_user"
SCHEMA_WS_CURRENT_USER = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_CURRENT_USER}
)

WS_TYPE_LONG_LIVED_ACCESS_TOKEN = "auth/long_lived_access_token"
SCHEMA_WS_LONG_LIVED_ACCESS_TOKEN = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_LONG_LIVED_ACCESS_TOKEN,
        vol.Required("lifespan"): int,  # days
        vol.Required("client_name"): str,
        vol.Optional("client_icon"): str,
    }
)

WS_TYPE_REFRESH_TOKENS = "auth/refresh_tokens"
SCHEMA_WS_REFRESH_TOKENS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_REFRESH_TOKENS}
)

WS_TYPE_DELETE_REFRESH_TOKEN = "auth/delete_refresh_token"
SCHEMA_WS_DELETE_REFRESH_TOKEN = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_DELETE_REFRESH_TOKEN,
        vol.Required("refresh_token_id"): str,
    }
)

WS_TYPE_SIGN_PATH = "auth/sign_path"
SCHEMA_WS_SIGN_PATH = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_SIGN_PATH,
        vol.Required("path"): str,
        vol.Optional("expires", default=30): int,
    }
)

RESULT_TYPE_CREDENTIALS = "credentials"
RESULT_TYPE_USER = "user"

_LOGGER = logging.getLogger(__name__)


@bind_hass
def create_auth_code(hass, client_id: str, user: User) -> str:
    """Create an authorization code to fetch tokens."""
    return hass.data[DOMAIN](client_id, user)


async def async_setup(hass, config):
    """Component to allow users to login."""
    store_result, retrieve_result = _create_auth_code_store()

    hass.data[DOMAIN] = store_result

    hass.http.register_view(TokenView(retrieve_result))
    hass.http.register_view(LinkUserView(retrieve_result))

    hass.components.websocket_api.async_register_command(
        WS_TYPE_CURRENT_USER, websocket_current_user, SCHEMA_WS_CURRENT_USER
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_LONG_LIVED_ACCESS_TOKEN,
        websocket_create_long_lived_access_token,
        SCHEMA_WS_LONG_LIVED_ACCESS_TOKEN,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_REFRESH_TOKENS, websocket_refresh_tokens, SCHEMA_WS_REFRESH_TOKENS
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_DELETE_REFRESH_TOKEN,
        websocket_delete_refresh_token,
        SCHEMA_WS_DELETE_REFRESH_TOKEN,
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SIGN_PATH, websocket_sign_path, SCHEMA_WS_SIGN_PATH
    )

    await login_flow.async_setup(hass, store_result)
    await mfa_setup_flow.async_setup(hass)

    return True


class TokenView(HomeAssistantView):
    """View to issue or revoke tokens."""

    url = "/auth/token"
    name = "api:auth:token"
    requires_auth = False
    cors_allowed = True

    def __init__(self, retrieve_user):
        """Initialize the token view."""
        self._retrieve_user = retrieve_user

    @log_invalid_auth
    async def post(self, request):
        """Grant a token."""
        hass = request.app["hass"]
        data = await request.post()

        grant_type = data.get("grant_type")

        # IndieAuth 6.3.5
        # The revocation endpoint is the same as the token endpoint.
        # The revocation request includes an additional parameter,
        # action=revoke.
        if data.get("action") == "revoke":
            return await self._async_handle_revoke_token(hass, data)

        if grant_type == "authorization_code":
            return await self._async_handle_auth_code(hass, data, request.remote)

        if grant_type == "refresh_token":
            return await self._async_handle_refresh_token(hass, data, request.remote)

        return self.json(
            {"error": "unsupported_grant_type"}, status_code=HTTP_BAD_REQUEST
        )

    async def _async_handle_revoke_token(self, hass, data):
        """Handle revoke token request."""
        # OAuth 2.0 Token Revocation [RFC7009]
        # 2.2 The authorization server responds with HTTP status code 200
        # if the token has been revoked successfully or if the client
        # submitted an invalid token.
        token = data.get("token")

        if token is None:
            return web.Response(status=HTTP_OK)

        refresh_token = await hass.auth.async_get_refresh_token_by_token(token)

        if refresh_token is None:
            return web.Response(status=HTTP_OK)

        await hass.auth.async_remove_refresh_token(refresh_token)
        return web.Response(status=HTTP_OK)

    async def _async_handle_auth_code(self, hass, data, remote_addr):
        """Handle authorization code request."""
        client_id = data.get("client_id")
        if client_id is None or not indieauth.verify_client_id(client_id):
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid client id"},
                status_code=HTTP_BAD_REQUEST,
            )

        code = data.get("code")

        if code is None:
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid code"},
                status_code=HTTP_BAD_REQUEST,
            )

        user = self._retrieve_user(client_id, RESULT_TYPE_USER, code)

        if user is None or not isinstance(user, User):
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid code"},
                status_code=HTTP_BAD_REQUEST,
            )

        # refresh user
        user = await hass.auth.async_get_user(user.id)

        if not user.is_active:
            return self.json(
                {"error": "access_denied", "error_description": "User is not active"},
                status_code=HTTP_FORBIDDEN,
            )

        refresh_token = await hass.auth.async_create_refresh_token(user, client_id)
        access_token = hass.auth.async_create_access_token(refresh_token, remote_addr)

        return self.json(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "refresh_token": refresh_token.token,
                "expires_in": int(
                    refresh_token.access_token_expiration.total_seconds()
                ),
            }
        )

    async def _async_handle_refresh_token(self, hass, data, remote_addr):
        """Handle authorization code request."""
        client_id = data.get("client_id")
        if client_id is not None and not indieauth.verify_client_id(client_id):
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid client id"},
                status_code=HTTP_BAD_REQUEST,
            )

        token = data.get("refresh_token")

        if token is None:
            return self.json({"error": "invalid_request"}, status_code=HTTP_BAD_REQUEST)

        refresh_token = await hass.auth.async_get_refresh_token_by_token(token)

        if refresh_token is None:
            return self.json({"error": "invalid_grant"}, status_code=HTTP_BAD_REQUEST)

        if refresh_token.client_id != client_id:
            return self.json({"error": "invalid_request"}, status_code=HTTP_BAD_REQUEST)

        access_token = hass.auth.async_create_access_token(refresh_token, remote_addr)

        return self.json(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": int(
                    refresh_token.access_token_expiration.total_seconds()
                ),
            }
        )


class LinkUserView(HomeAssistantView):
    """View to link existing users to new credentials."""

    url = "/auth/link_user"
    name = "api:auth:link_user"

    def __init__(self, retrieve_credentials):
        """Initialize the link user view."""
        self._retrieve_credentials = retrieve_credentials

    @RequestDataValidator(vol.Schema({"code": str, "client_id": str}))
    async def post(self, request, data):
        """Link a user."""
        hass = request.app["hass"]
        user = request["hass_user"]

        credentials = self._retrieve_credentials(
            data["client_id"], RESULT_TYPE_CREDENTIALS, data["code"]
        )

        if credentials is None:
            return self.json_message("Invalid code", status_code=HTTP_BAD_REQUEST)

        await hass.auth.async_link_user(user, credentials)
        return self.json_message("User linked")


@callback
def _create_auth_code_store():
    """Create an in memory store."""
    temp_results = {}

    @callback
    def store_result(client_id, result):
        """Store flow result and return a code to retrieve it."""
        if isinstance(result, User):
            result_type = RESULT_TYPE_USER
        elif isinstance(result, Credentials):
            result_type = RESULT_TYPE_CREDENTIALS
        else:
            raise ValueError("result has to be either User or Credentials")

        code = uuid.uuid4().hex
        temp_results[(client_id, result_type, code)] = (
            dt_util.utcnow(),
            result_type,
            result,
        )
        return code

    @callback
    def retrieve_result(client_id, result_type, code):
        """Retrieve flow result."""
        key = (client_id, result_type, code)

        if key not in temp_results:
            return None

        created, _, result = temp_results.pop(key)

        # OAuth 4.2.1
        # The authorization code MUST expire shortly after it is issued to
        # mitigate the risk of leaks.  A maximum authorization code lifetime of
        # 10 minutes is RECOMMENDED.
        if dt_util.utcnow() - created < timedelta(minutes=10):
            return result

        return None

    return store_result, retrieve_result


@websocket_api.ws_require_user()
@websocket_api.async_response
async def websocket_current_user(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Return the current user."""
    user = connection.user
    enabled_modules = await hass.auth.async_get_enabled_mfa(user)

    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "id": user.id,
                "name": user.name,
                "is_owner": user.is_owner,
                "is_admin": user.is_admin,
                "credentials": [
                    {
                        "auth_provider_type": c.auth_provider_type,
                        "auth_provider_id": c.auth_provider_id,
                    }
                    for c in user.credentials
                ],
                "mfa_modules": [
                    {
                        "id": module.id,
                        "name": module.name,
                        "enabled": module.id in enabled_modules,
                    }
                    for module in hass.auth.auth_mfa_modules
                ],
            },
        )
    )


@websocket_api.ws_require_user()
@websocket_api.async_response
async def websocket_create_long_lived_access_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Create or a long-lived access token."""
    refresh_token = await hass.auth.async_create_refresh_token(
        connection.user,
        client_name=msg["client_name"],
        client_icon=msg.get("client_icon"),
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=msg["lifespan"]),
    )

    access_token = hass.auth.async_create_access_token(refresh_token)

    connection.send_message(websocket_api.result_message(msg["id"], access_token))


@websocket_api.ws_require_user()
@callback
def websocket_refresh_tokens(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Return metadata of users refresh tokens."""
    current_id = connection.refresh_token_id
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            [
                {
                    "id": refresh.id,
                    "client_id": refresh.client_id,
                    "client_name": refresh.client_name,
                    "client_icon": refresh.client_icon,
                    "type": refresh.token_type,
                    "created_at": refresh.created_at,
                    "is_current": refresh.id == current_id,
                    "last_used_at": refresh.last_used_at,
                    "last_used_ip": refresh.last_used_ip,
                }
                for refresh in connection.user.refresh_tokens.values()
            ],
        )
    )


@websocket_api.ws_require_user()
@websocket_api.async_response
async def websocket_delete_refresh_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Handle a delete refresh token request."""
    refresh_token = connection.user.refresh_tokens.get(msg["refresh_token_id"])

    if refresh_token is None:
        return websocket_api.error_message(
            msg["id"], "invalid_token_id", "Received invalid token"
        )

    await hass.auth.async_remove_refresh_token(refresh_token)

    connection.send_message(websocket_api.result_message(msg["id"], {}))


@websocket_api.ws_require_user()
@callback
def websocket_sign_path(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg
):
    """Handle a sign path request."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "path": async_sign_path(
                    hass,
                    connection.refresh_token_id,
                    msg["path"],
                    timedelta(seconds=msg["expires"]),
                )
            },
        )
    )
