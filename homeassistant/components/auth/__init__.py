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
token. The value ha_auth_provider will contain the auth provider type that was
used to authorize the refresh token.

{
    "access_token": "ABCDEFGH",
    "expires_in": 1800,
    "refresh_token": "IJKLMNOPQRST",
    "token_type": "Bearer",
    "ha_auth_provider": "homeassistant"
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


# POST /auth/external/callback

This is an endpoint for OAuth2 Authorization callbacks used by integrations
that link accounts with other cloud providers using LocalOAuth2Implementation
as part of a config flow.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from http import HTTPStatus
from logging import getLogger
from typing import Any, cast
import uuid

from aiohttp import web
from multidict import MultiDictProxy
import voluptuous as vol

from homeassistant.auth import InvalidAuthError
from homeassistant.auth.models import (
    TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    Credentials,
    RefreshToken,
    User,
)
from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.auth import (
    async_sign_path,
    async_user_not_allowed_do_auth,
)
from homeassistant.components.http.ban import log_invalid_auth
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2AuthorizeCallbackView
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

from . import indieauth, login_flow, mfa_setup_flow

DOMAIN = "auth"
STRICT_CONNECTION_URL = "/auth/strict_connection/temp_token"

type StoreResultType = Callable[[str, Credentials], str]
type RetrieveResultType = Callable[[str, str], Credentials | None]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@bind_hass
def create_auth_code(
    hass: HomeAssistant, client_id: str, credential: Credentials
) -> str:
    """Create an authorization code to fetch tokens."""
    return cast(StoreResultType, hass.data[DOMAIN])(client_id, credential)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Component to allow users to login."""
    store_result, retrieve_result = _create_auth_code_store()

    hass.data[DOMAIN] = store_result

    hass.http.register_view(TokenView(retrieve_result))
    hass.http.register_view(RevokeTokenView())
    hass.http.register_view(LinkUserView(retrieve_result))
    hass.http.register_view(OAuth2AuthorizeCallbackView())
    hass.http.register_view(StrictConnectionTempTokenView())

    websocket_api.async_register_command(hass, websocket_current_user)
    websocket_api.async_register_command(hass, websocket_create_long_lived_access_token)
    websocket_api.async_register_command(hass, websocket_refresh_tokens)
    websocket_api.async_register_command(hass, websocket_delete_refresh_token)
    websocket_api.async_register_command(hass, websocket_delete_all_refresh_tokens)
    websocket_api.async_register_command(hass, websocket_sign_path)

    login_flow.async_setup(hass, store_result)
    mfa_setup_flow.async_setup(hass)

    return True


class RevokeTokenView(HomeAssistantView):
    """View to revoke tokens."""

    url = "/auth/revoke"
    name = "api:auth:revocation"
    requires_auth = False
    cors_allowed = True

    async def post(self, request: web.Request) -> web.Response:
        """Revoke a token."""
        hass = request.app[KEY_HASS]
        data = cast(MultiDictProxy[str], await request.post())

        # OAuth 2.0 Token Revocation [RFC7009]
        # 2.2 The authorization server responds with HTTP status code 200
        # if the token has been revoked successfully or if the client
        # submitted an invalid token.
        if (token := data.get("token")) is None:
            return web.Response(status=HTTPStatus.OK)

        refresh_token = hass.auth.async_get_refresh_token_by_token(token)

        if refresh_token is None:
            return web.Response(status=HTTPStatus.OK)

        hass.auth.async_remove_refresh_token(refresh_token)
        return web.Response(status=HTTPStatus.OK)


class TokenView(HomeAssistantView):
    """View to issue tokens."""

    url = "/auth/token"
    name = "api:auth:token"
    requires_auth = False
    cors_allowed = True

    def __init__(self, retrieve_auth: RetrieveResultType) -> None:
        """Initialize the token view."""
        self._retrieve_auth = retrieve_auth

    @log_invalid_auth
    async def post(self, request: web.Request) -> web.Response:
        """Grant a token."""
        hass = request.app[KEY_HASS]
        data = cast(MultiDictProxy[str], await request.post())

        grant_type = data.get("grant_type")

        # IndieAuth 6.3.5
        # The revocation endpoint is the same as the token endpoint.
        # The revocation request includes an additional parameter,
        # action=revoke.
        if data.get("action") == "revoke":
            # action=revoke is deprecated. Use /auth/revoke instead.
            # Keep here for backwards compat
            return await RevokeTokenView.post(self, request)  # type: ignore[arg-type]

        if grant_type == "authorization_code":
            return await self._async_handle_auth_code(hass, data, request)

        if grant_type == "refresh_token":
            return await self._async_handle_refresh_token(hass, data, request)

        return self.json(
            {"error": "unsupported_grant_type"}, status_code=HTTPStatus.BAD_REQUEST
        )

    async def _async_handle_auth_code(
        self,
        hass: HomeAssistant,
        data: MultiDictProxy[str],
        request: web.Request,
    ) -> web.Response:
        """Handle authorization code request."""
        client_id = data.get("client_id")
        if client_id is None or not indieauth.verify_client_id(client_id):
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid client id"},
                status_code=HTTPStatus.BAD_REQUEST,
            )

        if (code := data.get("code")) is None:
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid code"},
                status_code=HTTPStatus.BAD_REQUEST,
            )

        credential = self._retrieve_auth(client_id, code)

        if credential is None or not isinstance(credential, Credentials):
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid code"},
                status_code=HTTPStatus.BAD_REQUEST,
            )

        user = await hass.auth.async_get_or_create_user(credential)

        if user_access_error := async_user_not_allowed_do_auth(hass, user):
            return self.json(
                {
                    "error": "access_denied",
                    "error_description": user_access_error,
                },
                status_code=HTTPStatus.FORBIDDEN,
            )

        refresh_token = await hass.auth.async_create_refresh_token(
            user, client_id, credential=credential
        )
        try:
            access_token = hass.auth.async_create_access_token(
                refresh_token, request.remote
            )
        except InvalidAuthError as exc:
            return self.json(
                {"error": "access_denied", "error_description": str(exc)},
                status_code=HTTPStatus.FORBIDDEN,
            )

        await hass.auth.session.async_create_session(request, refresh_token)
        return self.json(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "refresh_token": refresh_token.token,
                "expires_in": int(
                    refresh_token.access_token_expiration.total_seconds()
                ),
                "ha_auth_provider": credential.auth_provider_type,
            },
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )

    async def _async_handle_refresh_token(
        self,
        hass: HomeAssistant,
        data: MultiDictProxy[str],
        request: web.Request,
    ) -> web.Response:
        """Handle refresh token request."""
        client_id = data.get("client_id")
        if client_id is not None and not indieauth.verify_client_id(client_id):
            return self.json(
                {"error": "invalid_request", "error_description": "Invalid client id"},
                status_code=HTTPStatus.BAD_REQUEST,
            )

        if (token := data.get("refresh_token")) is None:
            return self.json(
                {"error": "invalid_request"}, status_code=HTTPStatus.BAD_REQUEST
            )

        refresh_token = hass.auth.async_get_refresh_token_by_token(token)

        if refresh_token is None:
            return self.json(
                {"error": "invalid_grant"}, status_code=HTTPStatus.BAD_REQUEST
            )

        if refresh_token.client_id != client_id:
            return self.json(
                {"error": "invalid_request"}, status_code=HTTPStatus.BAD_REQUEST
            )

        if user_access_error := async_user_not_allowed_do_auth(
            hass, refresh_token.user
        ):
            return self.json(
                {
                    "error": "access_denied",
                    "error_description": user_access_error,
                },
                status_code=HTTPStatus.FORBIDDEN,
            )

        try:
            access_token = hass.auth.async_create_access_token(
                refresh_token, request.remote
            )
        except InvalidAuthError as exc:
            return self.json(
                {"error": "access_denied", "error_description": str(exc)},
                status_code=HTTPStatus.FORBIDDEN,
            )

        await hass.auth.session.async_create_session(request, refresh_token)
        return self.json(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": int(
                    refresh_token.access_token_expiration.total_seconds()
                ),
            },
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )


class LinkUserView(HomeAssistantView):
    """View to link existing users to new credentials."""

    url = "/auth/link_user"
    name = "api:auth:link_user"

    def __init__(self, retrieve_credentials: RetrieveResultType) -> None:
        """Initialize the link user view."""
        self._retrieve_credentials = retrieve_credentials

    @RequestDataValidator(vol.Schema({"code": str, "client_id": str}))
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Link a user."""
        hass = request.app[KEY_HASS]
        user: User = request["hass_user"]

        credentials = self._retrieve_credentials(data["client_id"], data["code"])

        if credentials is None:
            return self.json_message("Invalid code", status_code=HTTPStatus.BAD_REQUEST)

        linked_user = await hass.auth.async_get_user_by_credentials(credentials)
        if linked_user != user and linked_user is not None:
            return self.json_message(
                "Credential already linked", status_code=HTTPStatus.BAD_REQUEST
            )

        # No-op if credential is already linked to the user it will be linked to
        if linked_user != user:
            await hass.auth.async_link_user(user, credentials)
        return self.json_message("User linked")


class StrictConnectionTempTokenView(HomeAssistantView):
    """View to get temporary strict connection token."""

    url = STRICT_CONNECTION_URL
    name = "api:auth:strict_connection:temp_token"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Get a temporary token and redirect to main page."""
        hass = request.app[KEY_HASS]
        await hass.auth.session.async_create_temp_unauthorized_session(request)
        raise web.HTTPSeeOther(location="/")


@callback
def _create_auth_code_store() -> tuple[StoreResultType, RetrieveResultType]:
    """Create an in memory store."""
    temp_results: dict[tuple[str, str], tuple[datetime, Credentials]] = {}

    @callback
    def store_result(client_id: str, result: Credentials) -> str:
        """Store flow result and return a code to retrieve it."""
        if not isinstance(result, Credentials):
            raise TypeError("result has to be a Credentials instance")

        code = uuid.uuid4().hex
        temp_results[(client_id, code)] = (
            dt_util.utcnow(),
            result,
        )
        return code

    @callback
    def retrieve_result(client_id: str, code: str) -> Credentials | None:
        """Retrieve flow result."""
        key = (client_id, code)

        if key not in temp_results:
            return None

        created, result = temp_results.pop(key)

        # OAuth 4.2.1
        # The authorization code MUST expire shortly after it is issued to
        # mitigate the risk of leaks.  A maximum authorization code lifetime of
        # 10 minutes is RECOMMENDED.
        if dt_util.utcnow() - created < timedelta(minutes=10):
            return result

        return None

    return store_result, retrieve_result


@websocket_api.websocket_command({vol.Required("type"): "auth/current_user"})
@websocket_api.ws_require_user()
@websocket_api.async_response
async def websocket_current_user(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "auth/long_lived_access_token",
        vol.Required("lifespan"): int,  # days
        vol.Required("client_name"): str,
        vol.Optional("client_icon"): str,
    }
)
@websocket_api.ws_require_user()
@websocket_api.async_response
async def websocket_create_long_lived_access_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create or a long-lived access token."""
    refresh_token = await hass.auth.async_create_refresh_token(
        connection.user,
        client_name=msg["client_name"],
        client_icon=msg.get("client_icon"),
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=msg["lifespan"]),
    )

    try:
        access_token = hass.auth.async_create_access_token(refresh_token)
    except InvalidAuthError as exc:
        connection.send_error(msg["id"], websocket_api.const.ERR_UNAUTHORIZED, str(exc))
        return

    connection.send_result(msg["id"], access_token)


@websocket_api.websocket_command({vol.Required("type"): "auth/refresh_tokens"})
@websocket_api.ws_require_user()
@callback
def websocket_refresh_tokens(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return metadata of users refresh tokens."""
    current_id = connection.refresh_token_id

    tokens: list[dict[str, Any]] = []
    for refresh in connection.user.refresh_tokens.values():
        if refresh.credential:
            auth_provider_type = refresh.credential.auth_provider_type
        else:
            auth_provider_type = None

        tokens.append(
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
                "auth_provider_type": auth_provider_type,
            }
        )

    connection.send_result(msg["id"], tokens)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "auth/delete_refresh_token",
        vol.Required("refresh_token_id"): str,
    }
)
@websocket_api.ws_require_user()
def websocket_delete_refresh_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle a delete refresh token request."""
    refresh_token = connection.user.refresh_tokens.get(msg["refresh_token_id"])

    if refresh_token is None:
        connection.send_error(msg["id"], "invalid_token_id", "Received invalid token")
        return

    hass.auth.async_remove_refresh_token(refresh_token)

    connection.send_result(msg["id"], {})


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "auth/delete_all_refresh_tokens",
        vol.Optional("token_type"): cv.string,
        vol.Optional("delete_current_token", default=True): bool,
    }
)
@websocket_api.ws_require_user()
def websocket_delete_all_refresh_tokens(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle delete all refresh tokens request."""
    current_refresh_token: RefreshToken
    remove_failed = False
    token_type = msg.get("token_type")
    delete_current_token = msg.get("delete_current_token")
    limit_token_types = token_type is not None

    for token in list(connection.user.refresh_tokens.values()):
        if token.id == connection.refresh_token_id:
            # Skip the current refresh token as it has revoke_callback,
            # which cancels/closes the connection.
            # It will be removed after sending the result.
            current_refresh_token = token
            continue
        if limit_token_types and token_type != token.token_type:
            continue
        try:
            hass.auth.async_remove_refresh_token(token)
        except Exception:
            getLogger(__name__).exception("Error during refresh token removal")
            remove_failed = True

    if remove_failed:
        connection.send_error(
            msg["id"], "token_removing_error", "During removal, an error was raised."
        )
    else:
        connection.send_result(msg["id"], {})

    if delete_current_token and (
        not limit_token_types or current_refresh_token.token_type == token_type
    ):
        # This will close the connection so we need to send the result first.
        hass.loop.call_soon(hass.auth.async_remove_refresh_token, current_refresh_token)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "auth/sign_path",
        vol.Required("path"): str,
        vol.Optional("expires", default=30): int,
    }
)
@websocket_api.ws_require_user()
@callback
def websocket_sign_path(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle a sign path request."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "path": async_sign_path(
                    hass,
                    msg["path"],
                    timedelta(seconds=msg["expires"]),
                )
            },
        )
    )
