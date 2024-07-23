"""The tests for the Home Assistant HTTP component."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from http import HTTPStatus
from ipaddress import ip_network
import logging
from unittest.mock import Mock, patch

from aiohttp import BasicAuth, ServerDisconnectedError, web
from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp_session import get_session
import jwt
import pytest
import yarl
from yarl import URL

from homeassistant.auth.const import GROUP_ID_READ_ONLY
from homeassistant.auth.models import RefreshToken, User
from homeassistant.auth.providers import trusted_networks
from homeassistant.auth.providers.legacy_api_password import (
    LegacyApiPasswordAuthProvider,
)
from homeassistant.auth.session import SESSION_ID, TEMP_TIMEOUT
from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.auth import (
    CONTENT_USER_NAME,
    DATA_SIGN_SECRET,
    SIGN_QUERY_PARAM,
    STORAGE_KEY,
    STRICT_CONNECTION_GUARD_PAGE,
    async_setup_auth,
    async_sign_path,
    async_user_not_allowed_do_auth,
)
from homeassistant.components.http.const import KEY_AUTHENTICATED, StrictConnectionMode
from homeassistant.components.http.forwarded import async_setup_forwarded
from homeassistant.components.http.request_context import (
    current_request,
    setup_request_context,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import HTTP_HEADER_HA_AUTH

from tests.common import MockUser, async_fire_time_changed
from tests.test_util import mock_real_ip
from tests.typing import ClientSessionGenerator, WebSocketGenerator

_LOGGER = logging.getLogger(__name__)
API_PASSWORD = "test-password"

# Don't add 127.0.0.1/::1 as trusted, as it may interfere with other test cases
TRUSTED_NETWORKS = [
    ip_network("192.0.2.0/24"),
    ip_network("2001:DB8:ABCD::/48"),
    ip_network("100.64.0.1"),
    ip_network("FD01:DB8::1"),
]
TRUSTED_ADDRESSES = ["100.64.0.1", "192.0.2.100", "FD01:DB8::1", "2001:DB8:ABCD::1"]
EXTERNAL_ADDRESSES = ["198.51.100.1", "2001:DB8:FA1::1"]
LOCALHOST_ADDRESSES = ["127.0.0.1", "::1"]
UNTRUSTED_ADDRESSES = [*EXTERNAL_ADDRESSES, *LOCALHOST_ADDRESSES]
PRIVATE_ADDRESSES = [
    "192.168.10.10",
    "172.16.4.20",
    "10.100.50.5",
]


async def mock_handler(request):
    """Return if request was authenticated."""
    if not request[KEY_AUTHENTICATED]:
        raise HTTPUnauthorized

    user = request.get("hass_user")
    user_id = user.id if user else None

    return web.json_response(data={"user_id": user_id})


async def get_legacy_user(auth):
    """Get the user in legacy_api_password auth provider."""
    provider = auth.get_auth_provider("legacy_api_password", None)
    return await auth.async_get_or_create_user(
        await provider.async_get_or_create_credentials({})
    )


@pytest.fixture
def app(hass):
    """Fixture to set up a web.Application."""
    app = web.Application()
    app[KEY_HASS] = hass
    app.router.add_get("/", mock_handler)
    async_setup_forwarded(app, True, [])
    return app


@pytest.fixture
def app2(hass):
    """Fixture to set up a web.Application without real_ip middleware."""
    app = web.Application()
    app[KEY_HASS] = hass
    app.router.add_get("/", mock_handler)
    return app


@pytest.fixture
def trusted_networks_auth(hass):
    """Load trusted networks auth provider."""
    prv = trusted_networks.TrustedNetworksAuthProvider(
        hass,
        hass.auth._store,
        {"type": "trusted_networks", "trusted_networks": TRUSTED_NETWORKS},
    )
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


async def test_auth_middleware_loaded_by_default(hass: HomeAssistant) -> None:
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.async_setup_auth") as mock_setup:
        await async_setup_component(hass, "http", {"http": {}})

    assert len(mock_setup.mock_calls) == 1


async def test_cant_access_with_password_in_header(
    app,
    aiohttp_client: ClientSessionGenerator,
    legacy_auth: LegacyApiPasswordAuthProvider,
    hass: HomeAssistant,
) -> None:
    """Test access with password in header."""
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    req = await client.get("/", headers={HTTP_HEADER_HA_AUTH: API_PASSWORD})
    assert req.status == HTTPStatus.UNAUTHORIZED

    req = await client.get("/", headers={HTTP_HEADER_HA_AUTH: "wrong-pass"})
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_cant_access_with_password_in_query(
    app,
    aiohttp_client: ClientSessionGenerator,
    legacy_auth: LegacyApiPasswordAuthProvider,
    hass: HomeAssistant,
) -> None:
    """Test access with password in URL."""
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    resp = await client.get("/", params={"api_password": API_PASSWORD})
    assert resp.status == HTTPStatus.UNAUTHORIZED

    resp = await client.get("/")
    assert resp.status == HTTPStatus.UNAUTHORIZED

    resp = await client.get("/", params={"api_password": "wrong-password"})
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_basic_auth_does_not_work(
    app,
    aiohttp_client: ClientSessionGenerator,
    hass: HomeAssistant,
    legacy_auth: LegacyApiPasswordAuthProvider,
) -> None:
    """Test access with basic authentication."""
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    req = await client.get("/", auth=BasicAuth("homeassistant", API_PASSWORD))
    assert req.status == HTTPStatus.UNAUTHORIZED

    req = await client.get("/", auth=BasicAuth("wrong_username", API_PASSWORD))
    assert req.status == HTTPStatus.UNAUTHORIZED

    req = await client.get("/", auth=BasicAuth("homeassistant", "wrong password"))
    assert req.status == HTTPStatus.UNAUTHORIZED

    req = await client.get("/", headers={"authorization": "NotBasic abcdefg"})
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_cannot_access_with_trusted_ip(
    hass: HomeAssistant,
    app2,
    trusted_networks_auth,
    aiohttp_client: ClientSessionGenerator,
    hass_owner_user: MockUser,
) -> None:
    """Test access with an untrusted ip address."""
    await async_setup_auth(hass, app2, StrictConnectionMode.DISABLED)

    set_mock_ip = mock_real_ip(app2)
    client = await aiohttp_client(app2)

    for remote_addr in UNTRUSTED_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get("/")
        assert (
            resp.status == HTTPStatus.UNAUTHORIZED
        ), f"{remote_addr} shouldn't be trusted"

    for remote_addr in TRUSTED_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get("/")
        assert (
            resp.status == HTTPStatus.UNAUTHORIZED
        ), f"{remote_addr} shouldn't be trusted"


async def test_auth_active_access_with_access_token_in_header(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test access with access token in header."""
    token = hass_access_token
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    req = await client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert req.status == HTTPStatus.OK
    assert await req.json() == {"user_id": refresh_token.user.id}

    req = await client.get("/", headers={"AUTHORIZATION": f"Bearer {token}"})
    assert req.status == HTTPStatus.OK
    assert await req.json() == {"user_id": refresh_token.user.id}

    req = await client.get("/", headers={"authorization": f"Bearer {token}"})
    assert req.status == HTTPStatus.OK
    assert await req.json() == {"user_id": refresh_token.user.id}

    req = await client.get("/", headers={"Authorization": token})
    assert req.status == HTTPStatus.UNAUTHORIZED

    req = await client.get("/", headers={"Authorization": f"BEARER {token}"})
    assert req.status == HTTPStatus.UNAUTHORIZED

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    refresh_token.user.is_active = False
    req = await client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_auth_active_access_with_trusted_ip(
    hass: HomeAssistant,
    app2,
    trusted_networks_auth,
    aiohttp_client: ClientSessionGenerator,
    hass_owner_user: MockUser,
) -> None:
    """Test access with an untrusted ip address."""
    await async_setup_auth(hass, app2, StrictConnectionMode.DISABLED)

    set_mock_ip = mock_real_ip(app2)
    client = await aiohttp_client(app2)

    for remote_addr in UNTRUSTED_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get("/")
        assert (
            resp.status == HTTPStatus.UNAUTHORIZED
        ), f"{remote_addr} shouldn't be trusted"

    for remote_addr in TRUSTED_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get("/")
        assert (
            resp.status == HTTPStatus.UNAUTHORIZED
        ), f"{remote_addr} shouldn't be trusted"


async def test_auth_legacy_support_api_password_cannot_access(
    app,
    aiohttp_client: ClientSessionGenerator,
    legacy_auth: LegacyApiPasswordAuthProvider,
    hass: HomeAssistant,
) -> None:
    """Test access using api_password if auth.support_legacy."""
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    req = await client.get("/", headers={HTTP_HEADER_HA_AUTH: API_PASSWORD})
    assert req.status == HTTPStatus.UNAUTHORIZED

    resp = await client.get("/", params={"api_password": API_PASSWORD})
    assert resp.status == HTTPStatus.UNAUTHORIZED

    req = await client.get("/", auth=BasicAuth("homeassistant", API_PASSWORD))
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_auth_access_signed_path_with_refresh_token(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test access with signed url."""
    app.router.add_post("/", mock_handler)
    app.router.add_get("/another_path", mock_handler)
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    signed_path = async_sign_path(
        hass, "/", timedelta(seconds=5), refresh_token_id=refresh_token.id
    )

    req = await client.get(signed_path)
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data["user_id"] == refresh_token.user.id

    # Use signature on other path
    req = await client.get("/another_path?{}".format(signed_path.split("?")[1]))
    assert req.status == HTTPStatus.UNAUTHORIZED

    # We only allow GET
    req = await client.post(signed_path)
    assert req.status == HTTPStatus.UNAUTHORIZED

    # Never valid as expired in the past.
    expired_signed_path = async_sign_path(
        hass, "/", timedelta(seconds=-5), refresh_token_id=refresh_token.id
    )

    req = await client.get(expired_signed_path)
    assert req.status == HTTPStatus.UNAUTHORIZED

    # refresh token gone should also invalidate signature
    hass.auth.async_remove_refresh_token(refresh_token)
    req = await client.get(signed_path)
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_auth_access_signed_path_with_query_param(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test access with signed url and query params."""
    app.router.add_post("/", mock_handler)
    app.router.add_get("/another_path", mock_handler)
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    signed_path = async_sign_path(
        hass, "/?test=test", timedelta(seconds=5), refresh_token_id=refresh_token.id
    )

    req = await client.get(signed_path)
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data["user_id"] == refresh_token.user.id

    # Without query params not allowed
    url = yarl.URL(signed_path)
    signed_path = f"{url.path}?{SIGN_QUERY_PARAM}={url.query.get(SIGN_QUERY_PARAM)}"
    req = await client.get(signed_path)
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_auth_access_signed_path_with_query_param_order(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test access with signed url and query params different order."""
    app.router.add_post("/", mock_handler)
    app.router.add_get("/another_path", mock_handler)
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    signed_path = async_sign_path(
        hass,
        "/?test=test&foo=bar",
        timedelta(seconds=5),
        refresh_token_id=refresh_token.id,
    )
    url = yarl.URL(signed_path)

    # Change order
    req = await client.get(
        f"{url.path}?{SIGN_QUERY_PARAM}={url.query.get(SIGN_QUERY_PARAM)}&foo=bar&test=test"
    )
    assert req.status == HTTPStatus.UNAUTHORIZED

    # Duplicate a param
    req = await client.get(
        f"{url.path}?{SIGN_QUERY_PARAM}={url.query.get(SIGN_QUERY_PARAM)}&test=test&foo=aaa&foo=bar"
    )
    assert req.status == HTTPStatus.UNAUTHORIZED

    # Remove a param
    req = await client.get(
        f"{url.path}?{SIGN_QUERY_PARAM}={url.query.get(SIGN_QUERY_PARAM)}&test=test"
    )
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_auth_access_signed_path_with_query_param_safe_param(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test access with signed url and changing a safe param."""
    app.router.add_post("/", mock_handler)
    app.router.add_get("/another_path", mock_handler)
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    signed_path = async_sign_path(
        hass,
        "/?test=test&foo=bar",
        timedelta(seconds=5),
        refresh_token_id=refresh_token.id,
    )
    signed_path = f"{signed_path}&width=100"

    req = await client.get(signed_path)
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data["user_id"] == refresh_token.user.id


@pytest.mark.parametrize(
    ("base_url", "test_url"),
    [
        ("/?test=test", "/?test=test&foo=bar"),
        ("/", "/?test=test"),
        ("/?test=test&foo=bar", "/?test=test&foo=baz"),
        ("/?test=test&foo=bar", "/?test=test"),
    ],
)
async def test_auth_access_signed_path_with_query_param_tamper(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    base_url: str,
    test_url: str,
) -> None:
    """Test access with signed url and query params that have been tampered with."""
    app.router.add_post("/", mock_handler)
    app.router.add_get("/another_path", mock_handler)
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    signed_path = async_sign_path(
        hass, base_url, timedelta(seconds=5), refresh_token_id=refresh_token.id
    )
    url = yarl.URL(signed_path)
    token = url.query.get(SIGN_QUERY_PARAM)

    req = await client.get(f"{test_url}&{SIGN_QUERY_PARAM}={token}")
    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_auth_access_signed_path_via_websocket(
    hass: HomeAssistant,
    app,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test signed url via websockets uses connection user."""

    @websocket_api.websocket_command({"type": "diagnostics/list"})
    @callback
    def get_signed_path(hass, connection, msg):
        connection.send_result(
            msg["id"], {"path": async_sign_path(hass, "/", timedelta(seconds=5))}
        )

    websocket_api.async_register_command(hass, get_signed_path)

    # We use hass_read_only_access_token to make sure the connection WS is used.
    client = await hass_ws_client(access_token=hass_read_only_access_token)

    await client.send_json({"id": 5, "type": "diagnostics/list"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]

    refresh_token = hass.auth.async_validate_access_token(hass_read_only_access_token)
    signature = yarl.URL(msg["result"]["path"]).query["authSig"]
    claims = jwt.decode(
        signature,
        hass.data[DATA_SIGN_SECRET],
        algorithms=["HS256"],
        options={"verify_signature": False},
    )
    assert claims["iss"] == refresh_token.id


async def test_auth_access_signed_path_with_http(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test signed url via HTTP uses HTTP user."""
    setup_request_context(app, current_request)

    async def mock_handler(request):
        """Return signed path."""
        return web.json_response(
            data={"path": async_sign_path(hass, "/", timedelta(seconds=-5))}
        )

    app.router.add_get("/hello", mock_handler)
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    client = await aiohttp_client(app)

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    req = await client.get(
        "/hello", headers={"Authorization": f"Bearer {hass_access_token}"}
    )
    assert req.status == HTTPStatus.OK
    data = await req.json()
    signature = yarl.URL(data["path"]).query["authSig"]
    claims = jwt.decode(
        signature,
        hass.data[DATA_SIGN_SECRET],
        algorithms=["HS256"],
        options={"verify_signature": False},
    )
    assert claims["iss"] == refresh_token.id


async def test_auth_access_signed_path_with_content_user(
    hass: HomeAssistant, app, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test access signed url uses content user."""
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    signed_path = async_sign_path(hass, "/", timedelta(seconds=5))
    signature = yarl.URL(signed_path).query["authSig"]
    claims = jwt.decode(
        signature,
        hass.data[DATA_SIGN_SECRET],
        algorithms=["HS256"],
        options={"verify_signature": False},
    )
    assert claims["iss"] == hass.data[STORAGE_KEY]


async def test_local_only_user_rejected(
    hass: HomeAssistant,
    app,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test access with access token in header."""
    token = hass_access_token
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    set_mock_ip = mock_real_ip(app)
    client = await aiohttp_client(app)
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)

    req = await client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert req.status == HTTPStatus.OK
    assert await req.json() == {"user_id": refresh_token.user.id}

    refresh_token.user.local_only = True

    for remote_addr in EXTERNAL_ADDRESSES:
        set_mock_ip(remote_addr)
        req = await client.get("/", headers={"Authorization": f"Bearer {token}"})
        assert req.status == HTTPStatus.UNAUTHORIZED


async def test_async_user_not_allowed_do_auth(hass: HomeAssistant, app) -> None:
    """Test for not allowing auth."""
    user = await hass.auth.async_create_user("Hello")
    user.is_active = False

    # User not active
    assert async_user_not_allowed_do_auth(hass, user) == "User is not active"

    user.is_active = True
    user.local_only = True

    # No current request
    assert (
        async_user_not_allowed_do_auth(hass, user)
        == "No request available to validate local access"
    )

    trusted_request = Mock(remote="192.168.1.123")
    untrusted_request = Mock(remote=UNTRUSTED_ADDRESSES[0])

    # Is Remote IP and local only (cloud not loaded)
    assert async_user_not_allowed_do_auth(hass, user, trusted_request) is None
    assert (
        async_user_not_allowed_do_auth(hass, user, untrusted_request)
        == "User cannot authenticate remotely"
    )

    # Mimic cloud loaded and validate local IP again
    hass.config.components.add("cloud")
    assert async_user_not_allowed_do_auth(hass, user, trusted_request) is None
    assert (
        async_user_not_allowed_do_auth(hass, user, untrusted_request)
        == "User cannot authenticate remotely"
    )

    # Is Cloud request and local only, even a local IP will fail
    with patch(
        "hass_nabucasa.remote.is_cloud_request", Mock(get=Mock(return_value=True))
    ):
        assert (
            async_user_not_allowed_do_auth(hass, user, trusted_request)
            == "User is local only"
        )


async def test_create_user_once(hass: HomeAssistant) -> None:
    """Test that we reuse the user."""
    cur_users = len(await hass.auth.async_get_users())
    app = web.Application()
    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)
    users = await hass.auth.async_get_users()
    assert len(users) == cur_users + 1

    user: User = next((user for user in users if user.name == CONTENT_USER_NAME), None)
    assert user is not None, users

    assert len(user.groups) == 1
    assert user.groups[0].id == GROUP_ID_READ_ONLY
    assert len(user.refresh_tokens) == 1
    assert user.system_generated

    await async_setup_auth(hass, app, StrictConnectionMode.DISABLED)

    # test it did not create a user
    assert len(await hass.auth.async_get_users()) == cur_users + 1


@pytest.fixture
def app_strict_connection(hass):
    """Fixture to set up a web.Application."""

    async def handler(request):
        """Return if request was authenticated."""
        return web.json_response(data={"authenticated": request[KEY_AUTHENTICATED]})

    app = web.Application()
    app[KEY_HASS] = hass
    app.router.add_get("/", handler)
    async_setup_forwarded(app, True, [])
    return app


@pytest.mark.parametrize(
    "strict_connection_mode", [e.value for e in StrictConnectionMode]
)
async def test_strict_connection_non_cloud_authenticated_requests(
    hass: HomeAssistant,
    app_strict_connection: web.Application,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    strict_connection_mode: StrictConnectionMode,
) -> None:
    """Test authenticated requests with strict connection."""
    token = hass_access_token
    await async_setup_auth(hass, app_strict_connection, strict_connection_mode)
    set_mock_ip = mock_real_ip(app_strict_connection)
    client = await aiohttp_client(app_strict_connection)
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    assert refresh_token
    assert hass.auth.session._strict_connection_sessions == {}

    signed_path = async_sign_path(
        hass, "/", timedelta(seconds=5), refresh_token_id=refresh_token.id
    )

    for remote_addr in (*LOCALHOST_ADDRESSES, *PRIVATE_ADDRESSES, *EXTERNAL_ADDRESSES):
        set_mock_ip(remote_addr)

        # authorized requests should work normally
        req = await client.get("/", headers={"Authorization": f"Bearer {token}"})
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": True}
        req = await client.get(signed_path)
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": True}


@pytest.mark.parametrize(
    "strict_connection_mode", [e.value for e in StrictConnectionMode]
)
async def test_strict_connection_non_cloud_local_unauthenticated_requests(
    hass: HomeAssistant,
    app_strict_connection: web.Application,
    aiohttp_client: ClientSessionGenerator,
    strict_connection_mode: StrictConnectionMode,
) -> None:
    """Test local unauthenticated requests with strict connection."""
    await async_setup_auth(hass, app_strict_connection, strict_connection_mode)
    set_mock_ip = mock_real_ip(app_strict_connection)
    client = await aiohttp_client(app_strict_connection)
    assert hass.auth.session._strict_connection_sessions == {}

    for remote_addr in (*LOCALHOST_ADDRESSES, *PRIVATE_ADDRESSES):
        set_mock_ip(remote_addr)
        # local requests should work normally
        req = await client.get("/")
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": False}


def _add_set_cookie_endpoint(app: web.Application, refresh_token: RefreshToken) -> None:
    """Add an endpoint to set a cookie."""

    async def set_cookie(request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        # Clear all sessions
        hass.auth.session._temp_sessions.clear()
        hass.auth.session._strict_connection_sessions.clear()

        if request.query["token"] == "refresh":
            await hass.auth.session.async_create_session(request, refresh_token)
        else:
            await hass.auth.session.async_create_temp_unauthorized_session(request)
        session = await get_session(request)
        return web.Response(text=session[SESSION_ID])

    app.router.add_get("/test/cookie", set_cookie)


async def _test_strict_connection_non_cloud_enabled_setup(
    hass: HomeAssistant,
    app: web.Application,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    strict_connection_mode: StrictConnectionMode,
) -> tuple[TestClient, Callable[[str], None], RefreshToken]:
    """Test external unauthenticated requests with strict connection non cloud enabled."""
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    assert refresh_token
    session = hass.auth.session
    assert session._strict_connection_sessions == {}
    assert session._temp_sessions == {}

    _add_set_cookie_endpoint(app, refresh_token)
    await async_setup_auth(hass, app, strict_connection_mode)
    set_mock_ip = mock_real_ip(app)
    client = await aiohttp_client(app)
    return (client, set_mock_ip, refresh_token)


async def _test_strict_connection_non_cloud_enabled_external_unauthenticated_requests(
    hass: HomeAssistant,
    app: web.Application,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    perform_unauthenticated_request: Callable[
        [HomeAssistant, TestClient], Awaitable[None]
    ],
    strict_connection_mode: StrictConnectionMode,
) -> None:
    """Test external unauthenticated requests with strict connection non cloud enabled."""
    client, set_mock_ip, _ = await _test_strict_connection_non_cloud_enabled_setup(
        hass, app, aiohttp_client, hass_access_token, strict_connection_mode
    )

    for remote_addr in EXTERNAL_ADDRESSES:
        set_mock_ip(remote_addr)
        await perform_unauthenticated_request(hass, client)


async def _test_strict_connection_non_cloud_enabled_external_unauthenticated_requests_refresh_token(
    hass: HomeAssistant,
    app: web.Application,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    perform_unauthenticated_request: Callable[
        [HomeAssistant, TestClient], Awaitable[None]
    ],
    strict_connection_mode: StrictConnectionMode,
) -> None:
    """Test external unauthenticated requests with strict connection non cloud enabled and refresh token cookie."""
    (
        client,
        set_mock_ip,
        refresh_token,
    ) = await _test_strict_connection_non_cloud_enabled_setup(
        hass, app, aiohttp_client, hass_access_token, strict_connection_mode
    )
    session = hass.auth.session

    # set strict connection cookie with refresh token
    set_mock_ip(LOCALHOST_ADDRESSES[0])
    session_id = await (await client.get("/test/cookie?token=refresh")).text()
    assert session._strict_connection_sessions == {session_id: refresh_token.id}
    for remote_addr in EXTERNAL_ADDRESSES:
        set_mock_ip(remote_addr)
        req = await client.get("/")
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": False}

    # Invalidate refresh token, which should also invalidate session
    hass.auth.async_remove_refresh_token(refresh_token)
    assert session._strict_connection_sessions == {}
    for remote_addr in EXTERNAL_ADDRESSES:
        set_mock_ip(remote_addr)
        await perform_unauthenticated_request(hass, client)


async def _test_strict_connection_non_cloud_enabled_external_unauthenticated_requests_temp_session(
    hass: HomeAssistant,
    app: web.Application,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    perform_unauthenticated_request: Callable[
        [HomeAssistant, TestClient], Awaitable[None]
    ],
    strict_connection_mode: StrictConnectionMode,
) -> None:
    """Test external unauthenticated requests with strict connection non cloud enabled and temp cookie."""
    client, set_mock_ip, _ = await _test_strict_connection_non_cloud_enabled_setup(
        hass, app, aiohttp_client, hass_access_token, strict_connection_mode
    )
    session = hass.auth.session

    # set strict connection cookie with temp session
    assert session._temp_sessions == {}
    set_mock_ip(LOCALHOST_ADDRESSES[0])
    session_id = await (await client.get("/test/cookie?token=temp")).text()
    assert client.session.cookie_jar.filter_cookies(URL("http://127.0.0.1"))
    assert session_id in session._temp_sessions
    for remote_addr in EXTERNAL_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.OK
        assert await resp.json() == {"authenticated": False}

    async_fire_time_changed(hass, utcnow() + TEMP_TIMEOUT + timedelta(minutes=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert session._temp_sessions == {}
    for remote_addr in EXTERNAL_ADDRESSES:
        set_mock_ip(remote_addr)
        await perform_unauthenticated_request(hass, client)


async def _drop_connection_unauthorized_request(
    _: HomeAssistant, client: TestClient
) -> None:
    with pytest.raises(ServerDisconnectedError):
        # unauthorized requests should raise ServerDisconnectedError
        await client.get("/")


async def _guard_page_unauthorized_request(
    hass: HomeAssistant, client: TestClient
) -> None:
    req = await client.get("/")
    assert req.status == HTTPStatus.IM_A_TEAPOT

    def read_guard_page() -> str:
        with open(STRICT_CONNECTION_GUARD_PAGE, encoding="utf-8") as file:
            return file.read()

    assert await req.text() == await hass.async_add_executor_job(read_guard_page)


@pytest.mark.parametrize(
    "test_func",
    [
        _test_strict_connection_non_cloud_enabled_external_unauthenticated_requests,
        _test_strict_connection_non_cloud_enabled_external_unauthenticated_requests_refresh_token,
        _test_strict_connection_non_cloud_enabled_external_unauthenticated_requests_temp_session,
    ],
    ids=[
        "no cookie",
        "refresh token cookie",
        "temp session cookie",
    ],
)
@pytest.mark.parametrize(
    ("strict_connection_mode", "request_func"),
    [
        (StrictConnectionMode.DROP_CONNECTION, _drop_connection_unauthorized_request),
        (StrictConnectionMode.GUARD_PAGE, _guard_page_unauthorized_request),
    ],
    ids=["drop connection", "static page"],
)
async def test_strict_connection_non_cloud_external_unauthenticated_requests(
    hass: HomeAssistant,
    app_strict_connection: web.Application,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    test_func: Callable[
        [
            HomeAssistant,
            web.Application,
            ClientSessionGenerator,
            str,
            Callable[[HomeAssistant, TestClient], Awaitable[None]],
            StrictConnectionMode,
        ],
        Awaitable[None],
    ],
    strict_connection_mode: StrictConnectionMode,
    request_func: Callable[[HomeAssistant, TestClient], Awaitable[None]],
) -> None:
    """Test external unauthenticated requests with strict connection non cloud."""
    await test_func(
        hass,
        app_strict_connection,
        aiohttp_client,
        hass_access_token,
        request_func,
        strict_connection_mode,
    )
