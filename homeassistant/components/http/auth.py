"""Authentication for HTTP component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from http import HTTPStatus
from ipaddress import ip_address
import logging
import os
import secrets
import time
from typing import Any, Final

from aiohttp import hdrs
from aiohttp.web import Application, Request, Response, StreamResponse, middleware
from aiohttp.web_exceptions import HTTPBadRequest
from aiohttp_session import session_middleware
import jwt
from jwt import api_jws
from yarl import URL

from homeassistant.auth import jwt_wrapper
from homeassistant.auth.const import GROUP_ID_READ_ONLY
from homeassistant.auth.models import User
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton
from homeassistant.helpers.http import current_request
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.network import is_cloud_connection
from homeassistant.helpers.storage import Store
from homeassistant.util.network import is_local

from .const import (
    DOMAIN,
    KEY_AUTHENTICATED,
    KEY_HASS_REFRESH_TOKEN_ID,
    KEY_HASS_USER,
    StrictConnectionMode,
)
from .session import HomeAssistantCookieStorage

_LOGGER = logging.getLogger(__name__)

DATA_API_PASSWORD: Final = "api_password"
DATA_SIGN_SECRET: Final = "http.auth.sign_secret"
SIGN_QUERY_PARAM: Final = "authSig"
SAFE_QUERY_PARAMS: Final = ["height", "width"]

STORAGE_VERSION = 1
STORAGE_KEY = "http.auth"
CONTENT_USER_NAME = "Home Assistant Content"
STRICT_CONNECTION_EXCLUDED_PATH = "/api/webhook/"
STRICT_CONNECTION_GUARD_PAGE_NAME = "strict_connection_guard_page.html"
STRICT_CONNECTION_GUARD_PAGE = os.path.join(
    os.path.dirname(__file__), STRICT_CONNECTION_GUARD_PAGE_NAME
)


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
    strict_connection_mode_non_cloud: StrictConnectionMode,
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

    if strict_connection_mode_non_cloud is StrictConnectionMode.GUARD_PAGE:
        # Load the guard page content on setup
        await _read_strict_connection_guard_page(hass)

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

        if not authenticated and not request.path.startswith(
            STRICT_CONNECTION_EXCLUDED_PATH
        ):
            strict_connection_mode = strict_connection_mode_non_cloud
            strict_connection_func = (
                _async_perform_strict_connection_action_on_non_local
            )
            if is_cloud_connection(hass):
                from homeassistant.components.cloud.util import (  # pylint: disable=import-outside-toplevel
                    get_strict_connection_mode,
                )

                strict_connection_mode = get_strict_connection_mode(hass)
                strict_connection_func = _async_perform_strict_connection_action

            if (
                strict_connection_mode is not StrictConnectionMode.DISABLED
                and not await hass.auth.session.async_validate_request_for_strict_connection_session(
                    request
                )
                and (
                    resp := await strict_connection_func(
                        hass,
                        request,
                        strict_connection_mode is StrictConnectionMode.GUARD_PAGE,
                    )
                )
                is not None
            ):
                return resp

        if authenticated and _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Authenticated %s for %s using %s",
                request.remote,
                request.path,
                auth_type,
            )

        request[KEY_AUTHENTICATED] = authenticated
        return await handler(request)

    app.middlewares.append(session_middleware(HomeAssistantCookieStorage(hass)))
    app.middlewares.append(auth_middleware)


async def _async_perform_strict_connection_action_on_non_local(
    hass: HomeAssistant,
    request: Request,
    guard_page: bool,
) -> StreamResponse | None:
    """Perform strict connection mode action if the request is not local.

    The function does the following:
    - Try to get the IP address of the request. If it fails, assume it's not local
    - If the request is local, return None (allow the request to continue)
    - If guard_page is True, return a response with the content
    - Otherwise close the connection and raise an exception
    """
    try:
        ip_address_ = ip_address(request.remote)  # type: ignore[arg-type]
    except ValueError:
        _LOGGER.debug("Invalid IP address: %s", request.remote)
        ip_address_ = None

    if ip_address_ and is_local(ip_address_):
        return None

    return await _async_perform_strict_connection_action(hass, request, guard_page)


async def _async_perform_strict_connection_action(
    hass: HomeAssistant,
    request: Request,
    guard_page: bool,
) -> StreamResponse | None:
    """Perform strict connection mode action.

    The function does the following:
    - If guard_page is True, return a response with the content
    - Otherwise close the connection and raise an exception
    """

    _LOGGER.debug("Perform strict connection action for %s", request.remote)
    if guard_page:
        return Response(
            text=await _read_strict_connection_guard_page(hass),
            content_type="text/html",
            status=HTTPStatus.IM_A_TEAPOT,
        )

    if transport := request.transport:
        # it should never happen that we don't have a transport
        transport.close()

    # We need to raise an exception to stop processing the request
    raise HTTPBadRequest


@singleton.singleton(f"{DOMAIN}_{STRICT_CONNECTION_GUARD_PAGE_NAME}")
async def _read_strict_connection_guard_page(hass: HomeAssistant) -> str:
    """Read the strict connection guard page from disk via executor."""

    def read_guard_page() -> str:
        with open(STRICT_CONNECTION_GUARD_PAGE, encoding="utf-8") as file:
            return file.read()

    return await hass.async_add_executor_job(read_guard_page)
