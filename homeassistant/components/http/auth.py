"""Authentication for HTTP component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from ipaddress import ip_address
import logging
import secrets
import time
from typing import Any, Final

from aiohttp import hdrs
from aiohttp.web import Application, Request, StreamResponse, middleware
import jwt
from jwt import api_jws
from yarl import URL

from homeassistant.auth import jwt_wrapper
from homeassistant.auth.const import GROUP_ID_READ_ONLY
from homeassistant.auth.models import User
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.http import current_request
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.network import is_cloud_connection
from homeassistant.helpers.storage import Store
from homeassistant.util.network import is_local

from .const import KEY_AUTHENTICATED, KEY_HASS_REFRESH_TOKEN_ID, KEY_HASS_USER

_LOGGER = logging.getLogger(__name__)

DATA_API_PASSWORD: Final = "api_password"
DATA_SIGN_SECRET: Final = "http.auth.sign_secret"
SIGN_QUERY_PARAM: Final = "authSig"
SAFE_QUERY_PARAMS: Final = frozenset(("height", "width"))

STORAGE_VERSION = 1
STORAGE_KEY = "http.auth"
CONTENT_USER_NAME = "Home Assistant Content"


@callback
def async_sign_path(
    hass: HomeAssistant,
    path: str,
    expiration: timedelta,
    *,
    refresh_token_id: str | None = None,
    use_content_user: bool = False,
) -> str:
    """Sign a path for temporary access without auth header."""
    if (secret := hass.data.get(DATA_SIGN_SECRET)) is None:
        secret = hass.data[DATA_SIGN_SECRET] = secrets.token_hex()

    if refresh_token_id is None:
        if use_content_user:
            refresh_token_id = hass.data[STORAGE_KEY]
        elif connection := websocket_api.current_connection.get():
            refresh_token_id = connection.refresh_token_id
        elif (
            request := current_request.get()
        ) and KEY_HASS_REFRESH_TOKEN_ID in request:
            refresh_token_id = request[KEY_HASS_REFRESH_TOKEN_ID]
        else:
            refresh_token_id = hass.data[STORAGE_KEY]

    url = URL(path)
    now_timestamp = int(time.time())
    expiration_timestamp = now_timestamp + int(expiration.total_seconds())
    params = [itm for itm in url.query.items() if itm[0] not in SAFE_QUERY_PARAMS]
    json_payload = json_bytes(
        {
            "iss": refresh_token_id,
            "path": url.path,
            "params": params,
            "iat": now_timestamp,
            "exp": expiration_timestamp,
        }
    )
    encoded = api_jws.encode(json_payload, secret, "HS256")
    params.append((SIGN_QUERY_PARAM, encoded))
    url = url.with_query(params)
    return f"{url.path}?{url.query_string}"


@callback
def async_user_not_allowed_do_auth(
    hass: HomeAssistant, user: User, request: Request | None = None
) -> str | None:
    """Validate that user is not allowed to do auth things."""
    if not user.is_active:
        return "User is not active"

    if not user.local_only:
        return None

    # User is marked as local only, check if they are allowed to do auth
    if request is None:
        request = current_request.get()

    if not request:
        return "No request available to validate local access"

    if is_cloud_connection(hass):
        return "User is local only"

    try:
        remote_address = ip_address(request.remote)  # type: ignore[arg-type]
    except ValueError:
        return "Invalid remote IP"

    if is_local(remote_address):
        return None

    return "User cannot authenticate remotely"


async def async_setup_auth(
    hass: HomeAssistant,
    app: Application,
) -> None:
    """Create auth middleware for the app."""
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    if (data := await store.async_load()) is None:
        data = {}

    refresh_token = None
    if "content_user" in data:
        user = await hass.auth.async_get_user(data["content_user"])
        if user and user.refresh_tokens:
            refresh_token = list(user.refresh_tokens.values())[0]

    if refresh_token is None:
        user = await hass.auth.async_create_system_user(
            CONTENT_USER_NAME, group_ids=[GROUP_ID_READ_ONLY]
        )
        refresh_token = await hass.auth.async_create_refresh_token(user)
        data["content_user"] = user.id
        await store.async_save(data)

    hass.data[STORAGE_KEY] = refresh_token.id

    @callback
    def async_validate_auth_header(request: Request) -> bool:
        """Test authorization header against access token.

        Basic auth_type is legacy code, should be removed with api_password.
        """
        try:
            auth_type, auth_val = request.headers.get(hdrs.AUTHORIZATION, "").split(
                " ", 1
            )
        except ValueError:
            # If no space in authorization header
            return False

        if auth_type != "Bearer":
            return False

        refresh_token = hass.auth.async_validate_access_token(auth_val)

        if refresh_token is None:
            return False

        if async_user_not_allowed_do_auth(hass, refresh_token.user, request):
            return False

        request[KEY_HASS_USER] = refresh_token.user
        request[KEY_HASS_REFRESH_TOKEN_ID] = refresh_token.id
        return True

    @callback
    def async_validate_signed_request(request: Request) -> bool:
        """Validate a signed request."""
        if (secret := hass.data.get(DATA_SIGN_SECRET)) is None:
            return False

        if (signature := request.query.get(SIGN_QUERY_PARAM)) is None:
            return False

        try:
            claims = jwt_wrapper.verify_and_decode(
                signature, secret, algorithms=["HS256"], options={"verify_iss": False}
            )
        except jwt.InvalidTokenError:
            return False

        if claims["path"] != request.path:
            return False

        params = [
            list(itm)  # claims stores tuples as lists
            for itm in request.query.items()
            if itm[0] not in SAFE_QUERY_PARAMS and itm[0] != SIGN_QUERY_PARAM
        ]
        if claims["params"] != params:
            return False

        refresh_token = hass.auth.async_get_refresh_token(claims["iss"])

        if refresh_token is None:
            return False

        request[KEY_HASS_USER] = refresh_token.user
        request[KEY_HASS_REFRESH_TOKEN_ID] = refresh_token.id
        return True

    @middleware
    async def auth_middleware(
        request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]
    ) -> StreamResponse:
        """Authenticate as middleware."""
        authenticated = False

        if hdrs.AUTHORIZATION in request.headers and async_validate_auth_header(
            request
        ):
            authenticated = True
            auth_type = "bearer token"

        # We first start with a string check to avoid parsing query params
        # for every request.
        elif (
            request.method == "GET"
            and SIGN_QUERY_PARAM in request.query_string
            and async_validate_signed_request(request)
        ):
            authenticated = True
            auth_type = "signed request"

        if authenticated and _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Authenticated %s for %s using %s",
                request.remote,
                request.path,
                auth_type,
            )

        request[KEY_AUTHENTICATED] = authenticated
        return await handler(request)

    app.middlewares.append(auth_middleware)
