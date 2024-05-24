"""Test strict connection mode for cloud."""

from collections.abc import Awaitable, Callable, Coroutine, Generator
from contextlib import contextmanager
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ServerDisconnectedError, web
from aiohttp.test_utils import TestClient
from aiohttp_session import get_session
import pytest
from yarl import URL

from homeassistant.auth.models import RefreshToken
from homeassistant.auth.session import SESSION_ID, TEMP_TIMEOUT
from homeassistant.components.cloud.const import PREF_STRICT_CONNECTION
from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.auth import (
    STRICT_CONNECTION_GUARD_PAGE,
    async_setup_auth,
    async_sign_path,
)
from homeassistant.components.http.const import KEY_AUTHENTICATED, StrictConnectionMode
from homeassistant.components.http.session import COOKIE_NAME, PREFIXED_COOKIE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import is_cloud_connection
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def refresh_token(hass: HomeAssistant, hass_access_token: str) -> RefreshToken:
    """Return a refresh token."""
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    assert refresh_token
    session = hass.auth.session
    assert session._strict_connection_sessions == {}
    assert session._temp_sessions == {}
    return refresh_token


@contextmanager
def simulate_cloud_request() -> Generator[None, None, None]:
    """Simulate a cloud request."""
    with patch(
        "hass_nabucasa.remote.is_cloud_request", Mock(get=Mock(return_value=True))
    ):
        yield


@pytest.fixture
def app_strict_connection(
    hass: HomeAssistant, refresh_token: RefreshToken
) -> web.Application:
    """Fixture to set up a web.Application."""

    async def handler(request):
        """Return if request was authenticated."""
        return web.json_response(data={"authenticated": request[KEY_AUTHENTICATED]})

    app = web.Application()
    app[KEY_HASS] = hass
    app.router.add_get("/", handler)

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
    return app


@pytest.fixture(name="client")
async def set_up_fixture(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    app_strict_connection: web.Application,
    cloud: MagicMock,
    socket_enabled: None,
) -> TestClient:
    """Set up the fixture."""

    await async_setup_auth(hass, app_strict_connection, StrictConnectionMode.DISABLED)
    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()
    return await aiohttp_client(app_strict_connection)


@pytest.mark.parametrize(
    "strict_connection_mode", [e.value for e in StrictConnectionMode]
)
async def test_strict_connection_cloud_authenticated_requests(
    hass: HomeAssistant,
    client: TestClient,
    hass_access_token: str,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    refresh_token: RefreshToken,
    strict_connection_mode: StrictConnectionMode,
) -> None:
    """Test authenticated requests with strict connection."""
    assert hass.auth.session._strict_connection_sessions == {}

    signed_path = async_sign_path(
        hass, "/", timedelta(seconds=5), refresh_token_id=refresh_token.id
    )

    await set_cloud_prefs(
        {
            PREF_STRICT_CONNECTION: strict_connection_mode,
        }
    )

    with simulate_cloud_request():
        assert is_cloud_connection(hass)
        req = await client.get(
            "/", headers={"Authorization": f"Bearer {hass_access_token}"}
        )
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": True}
        req = await client.get(signed_path)
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": True}


async def _test_strict_connection_cloud_enabled_external_unauthenticated_requests(
    hass: HomeAssistant,
    client: TestClient,
    perform_unauthenticated_request: Callable[
        [HomeAssistant, TestClient], Awaitable[None]
    ],
    _: RefreshToken,
) -> None:
    """Test external unauthenticated requests with strict connection cloud enabled."""
    with simulate_cloud_request():
        assert is_cloud_connection(hass)
        await perform_unauthenticated_request(hass, client)


async def _test_strict_connection_cloud_enabled_external_unauthenticated_requests_refresh_token(
    hass: HomeAssistant,
    client: TestClient,
    perform_unauthenticated_request: Callable[
        [HomeAssistant, TestClient], Awaitable[None]
    ],
    refresh_token: RefreshToken,
) -> None:
    """Test external unauthenticated requests with strict connection cloud enabled and refresh token cookie."""
    session = hass.auth.session

    # set strict connection cookie with refresh token
    session_id = await _modify_cookie_for_cloud(client, "refresh")
    assert session._strict_connection_sessions == {session_id: refresh_token.id}
    with simulate_cloud_request():
        assert is_cloud_connection(hass)
        req = await client.get("/")
        assert req.status == HTTPStatus.OK
        assert await req.json() == {"authenticated": False}

        # Invalidate refresh token, which should also invalidate session
        hass.auth.async_remove_refresh_token(refresh_token)
        assert session._strict_connection_sessions == {}

        await perform_unauthenticated_request(hass, client)


async def _test_strict_connection_cloud_enabled_external_unauthenticated_requests_temp_session(
    hass: HomeAssistant,
    client: TestClient,
    perform_unauthenticated_request: Callable[
        [HomeAssistant, TestClient], Awaitable[None]
    ],
    _: RefreshToken,
) -> None:
    """Test external unauthenticated requests with strict connection cloud enabled and temp cookie."""
    session = hass.auth.session

    # set strict connection cookie with temp session
    assert session._temp_sessions == {}
    session_id = await _modify_cookie_for_cloud(client, "temp")
    assert session_id in session._temp_sessions
    with simulate_cloud_request():
        assert is_cloud_connection(hass)
        resp = await client.get("/")
        assert resp.status == HTTPStatus.OK
        assert await resp.json() == {"authenticated": False}

        async_fire_time_changed(hass, utcnow() + TEMP_TIMEOUT + timedelta(minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert session._temp_sessions == {}

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
        _test_strict_connection_cloud_enabled_external_unauthenticated_requests,
        _test_strict_connection_cloud_enabled_external_unauthenticated_requests_refresh_token,
        _test_strict_connection_cloud_enabled_external_unauthenticated_requests_temp_session,
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
async def test_strict_connection_cloud_external_unauthenticated_requests(
    hass: HomeAssistant,
    client: TestClient,
    refresh_token: RefreshToken,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    test_func: Callable[
        [
            HomeAssistant,
            TestClient,
            Callable[[HomeAssistant, TestClient], Awaitable[None]],
            RefreshToken,
        ],
        Awaitable[None],
    ],
    strict_connection_mode: StrictConnectionMode,
    request_func: Callable[[HomeAssistant, TestClient], Awaitable[None]],
) -> None:
    """Test external unauthenticated requests with strict connection cloud."""
    await set_cloud_prefs(
        {
            PREF_STRICT_CONNECTION: strict_connection_mode,
        }
    )

    await test_func(
        hass,
        client,
        request_func,
        refresh_token,
    )


async def _modify_cookie_for_cloud(client: TestClient, token_type: str) -> str:
    """Modify cookie for cloud."""
    # Cloud cookie has set secure=true and will not set on insecure connection
    # As we test with insecure connection, we need to set it manually
    # We get the session via http and modify the cookie name to the secure one
    session_id = await (await client.get(f"/test/cookie?token={token_type}")).text()
    cookie_jar = client.session.cookie_jar
    localhost = URL("http://127.0.0.1")
    cookie = cookie_jar.filter_cookies(localhost)[COOKIE_NAME].value
    assert cookie
    cookie_jar.clear()
    cookie_jar.update_cookies({PREFIXED_COOKIE_NAME: cookie}, localhost)
    return session_id
