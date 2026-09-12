"""Test the VRChat API client helpers."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import vrchatapi

from homeassistant.components.vrchat.api import (
    VRChatAPI,
    get_cookie_dict,
    make_cookie,
    set_cookie_dict,
    wrap_api_object,
)
from homeassistant.components.vrchat.const import (
    CONF_COOKIE_2FA,
    CONF_COOKIE_AUTH,
    VRCHAT_API_HOST,
)


def test_cookie_dict_omits_empty_cookies() -> None:
    """Test empty authentication cookies are neither copied nor restored."""
    api = cast(vrchatapi.ApiClient, Mock())
    cookie_jar = cast(Any, api.rest_client.cookie_jar)
    cookie_jar._cookies = {
        VRCHAT_API_HOST: {
            "/": {
                CONF_COOKIE_AUTH: make_cookie(CONF_COOKIE_AUTH, "auth-cookie"),
                CONF_COOKIE_2FA: make_cookie(CONF_COOKIE_2FA, ""),
            }
        }
    }

    cookie = get_cookie_dict(api)

    assert cookie == {CONF_COOKIE_AUTH: "auth-cookie"}

    set_cookie_dict(api, cookie)

    cookie_jar.set_cookie.assert_called_once()
    stored_cookie = cookie_jar.set_cookie.call_args.args[0]
    assert stored_cookie.name == CONF_COOKIE_AUTH
    assert stored_cookie.value == "auth-cookie"


async def test_api_wrapper_returns_raw_json() -> None:
    """Test API methods are wrapped to return decoded raw responses."""
    api = Mock()
    api.get_user = Mock()
    api.get_user_with_http_info = AsyncMock(
        return_value=Mock(raw_data='{"id": "usr_test"}')
    )

    wrapped = wrap_api_object(api)

    assert await wrapped.get_user("usr_test") == {"id": "usr_test"}
    api.get_user_with_http_info.assert_awaited_once_with("usr_test")
    assert wrapped.get_user is wrapped.get_user


async def test_api_methods_forward_to_services() -> None:
    """Test the high-level API methods forward their arguments."""
    api = object.__new__(VRChatAPI)
    auth_api = Mock(
        get_current_user=AsyncMock(return_value={"id": "usr_test"}),
        verify2_fa=AsyncMock(return_value=True),
        verify2_fa_email_code=AsyncMock(return_value=True),
        logout=AsyncMock(return_value=True),
    )
    friends_api = Mock(get_friends=AsyncMock(return_value=[]))
    users_api = Mock(
        get_user=AsyncMock(return_value={"id": "usr_test"}),
        update_user=AsyncMock(return_value={"id": "usr_test"}),
    )
    worlds_api = Mock(get_world=AsyncMock(return_value={"id": "wrld_test"}))
    api.__dict__.update(
        auth_api=auth_api,
        friends_api=friends_api,
        users_api=users_api,
        worlds_api=worlds_api,
    )

    request = Mock()
    assert await api.get_current_user() == {"id": "usr_test"}
    await api.verify2_fa("123456")
    await api.verify2_fa_email_code("654321")
    await api.get_friends(1, 2, True)
    await api.get_user("usr_test")
    await api.update_user("usr_test", request)
    await api.get_world("wrld_test")
    await api.logout()

    auth_api.verify2_fa.assert_awaited_once()
    assert auth_api.verify2_fa.await_args.args[0].code == "123456"
    auth_api.verify2_fa_email_code.assert_awaited_once()
    assert auth_api.verify2_fa_email_code.await_args.args[0].code == "654321"
    friends_api.get_friends.assert_awaited_once_with(offset=1, n=2, offline=True)
    users_api.get_user.assert_awaited_once_with("usr_test")
    users_api.update_user.assert_awaited_once_with(
        "usr_test", update_user_request=request
    )
    worlds_api.get_world.assert_awaited_once_with("wrld_test")


async def test_api_service_wrappers_and_websocket() -> None:
    """Test service wrappers are cached and WebSocket connections are tracked."""
    api = VRChatAPI()
    assert api.auth_api is api.auth_api
    assert api.friends_api is api.friends_api
    assert api.users_api is api.users_api
    assert api.worlds_api is api.worlds_api

    websocket = Mock()
    websocket.connect = AsyncMock()
    websocket.close = AsyncMock()
    with patch(
        "homeassistant.components.vrchat.api.VRChatWebSocket.from_client",
        return_value=websocket,
    ):
        connected = await api.ws_connect()

    assert connected is websocket
    websocket.connect.assert_awaited_once()
    assert websocket.close in api._cleanups


def test_api_cookie_clear_and_copy() -> None:
    """Test clearing cookies and copying the API preserves configuration."""
    api = VRChatAPI(
        {"username": "user", "password": "password"}, {CONF_COOKIE_AUTH: "auth"}
    )
    api.api_client.rest_client.cookie_jar.clear = Mock()

    copied = api.copy()
    api.clear_cookie()

    assert copied.config == api.config
    assert copied.cookie == api.cookie
    api.api_client.rest_client.cookie_jar.clear.assert_called_once_with()


def test_api_wrapper_returns_non_callable_attributes() -> None:
    """Test API wrapper leaves non-callable attributes unchanged."""
    wrapped = wrap_api_object(SimpleNamespace(value="test"))

    assert wrapped.value == "test"


def test_api_wrapper_returns_callable_without_raw_response_method() -> None:
    """Test API wrapper leaves non-endpoint methods unchanged."""
    method = Mock()
    wrapped = wrap_api_object(SimpleNamespace(method=method))

    assert wrapped.method is method
