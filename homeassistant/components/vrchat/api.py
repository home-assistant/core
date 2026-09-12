"""VRChat API."""

from functools import lru_cache, wraps
from http.cookiejar import Cookie
import json
from typing import Any, cast

from propcache.api import cached_property
import vrchatapi
from vrchatapi.websocket import VRChatWebSocket

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api_data_types import CurrentUser, User, World
from .const import (
    CONF_COOKIE_2FA,
    CONF_COOKIE_AUTH,
    USER_AGENT,
    VRCHAT_API_HOST,
    VRCHAT_WEBSOCKET_URL,
)
from .store import VRChatAuthCookie, VRChatConfigData
from .utils import AsyncCleanups


class VRChatAPI(AsyncCleanups):
    """VRChat API Object."""

    def __init__(
        self,
        config: VRChatConfigData | None = None,
        cookie: VRChatAuthCookie | None = None,
    ) -> None:
        """Create API client."""
        self._config = config
        api_config: vrchatapi.Configuration | None = None
        if config is not None:
            api_config = vrchatapi.Configuration(
                username=config.get(CONF_USERNAME), password=config.get(CONF_PASSWORD)
            )
        self.api_client = vrchatapi.ApiClient(api_config)
        self.api_client.user_agent = USER_AGENT
        self.add_to_cleanups(self.api_client.close)
        self.cookie = cookie

    @property
    def config(self):
        """Config that was used to create the API object.

        Mutating the config doesn't change the actual API config.
        Please create a new API object if change is needed.
        """
        return self._config

    @property
    def cookie(self):
        """Cookie dict."""
        return get_cookie_dict(self.api_client)

    @cookie.setter
    def cookie(self, new_cookie):
        set_cookie_dict(self.api_client, new_cookie)

    def clear_cookie(self):
        """Clear cookie."""
        self.api_client.rest_client.cookie_jar.clear()

    def copy(self):
        """Get a copy with the same config and cookies."""
        return VRChatAPI(self.config, self.cookie)

    @cached_property
    def auth_api(self):
        """Authentication API."""
        return wrap_api_object(vrchatapi.AuthenticationApi(self.api_client))

    @cached_property
    def friends_api(self):
        """Friends API."""
        return wrap_api_object(vrchatapi.FriendsApi(self.api_client))

    @cached_property
    def users_api(self):
        """Users API."""
        return wrap_api_object(vrchatapi.UsersApi(self.api_client))

    @cached_property
    def worlds_api(self):
        """Worlds API."""
        return wrap_api_object(vrchatapi.WorldsApi(self.api_client))

    async def get_current_user(self) -> CurrentUser:
        """Authenticate and get current user info."""
        return await self.auth_api.get_current_user()

    async def verify2_fa(self, code: str):
        """Verify 2FA code."""
        return await self.auth_api.verify2_fa(vrchatapi.TwoFactorAuthCode(code=code))

    async def verify2_fa_email_code(self, code: str):
        """Verify email 2FA code."""
        return await self.auth_api.verify2_fa_email_code(
            vrchatapi.TwoFactorEmailCode(code=code)
        )

    async def get_friends(self, offset: int, n: int, offline: bool) -> list[User]:
        """List friends."""
        return await self.friends_api.get_friends(offset=offset, n=n, offline=offline)

    async def get_user(self, user_id: str) -> User:
        """Get user by ID."""
        return await self.users_api.get_user(user_id)

    async def update_user(
        self, user_id: str, data: vrchatapi.UpdateUserRequest
    ) -> CurrentUser:
        """Update user info."""
        return await self.users_api.update_user(user_id, update_user_request=data)

    async def get_world(self, world_id: str) -> World:
        """Get world by ID."""
        return await self.worlds_api.get_world(world_id)

    async def ws_connect(self) -> VRChatWebSocket:
        """Get a websocket API connection."""
        ws = VRChatWebSocket.from_client(
            self.api_client, endpoint=VRCHAT_WEBSOCKET_URL, auto_reconnect=False
        )
        await ws.connect()
        self.add_to_cleanups(ws.close)
        return ws

    async def logout(self):
        """Log out."""
        return await self.auth_api.logout()


def make_cookie(name: str, value: str):
    """Make VRChat API cookie."""
    return Cookie(
        0,
        name,
        value,
        None,
        False,
        VRCHAT_API_HOST,
        True,
        False,
        "/",
        False,
        False,
        None,
        False,
        None,
        None,
        {},
    )


def set_cookie(api: vrchatapi.ApiClient, name: str, value: str | None = None):
    """Set a single cookie to VRChat API client."""
    if value:
        api.rest_client.cookie_jar.set_cookie(make_cookie(name, value))


def set_cookie_dict(api: vrchatapi.ApiClient, cookie: VRChatAuthCookie | None = None):
    """Set a cookie dict to VRChat API client."""
    if cookie is not None:
        set_cookie(api, CONF_COOKIE_AUTH, cookie.get(CONF_COOKIE_AUTH))
        set_cookie(api, CONF_COOKIE_2FA, cookie.get(CONF_COOKIE_2FA))


def get_cookie_dict(api: vrchatapi.ApiClient):
    """Get a cookie dict from VRChat API client."""
    cookie_jar_data = cast(Any, api.rest_client.cookie_jar)._cookies  # noqa: SLF001
    cookie_jar = cookie_jar_data.get(VRCHAT_API_HOST, {}).get("/", {})
    return {
        name: cookie.value
        for name in (CONF_COOKIE_AUTH, CONF_COOKIE_2FA)
        if (cookie := cookie_jar.get(name)) is not None and cookie.value
    }


def wrap_api_object[T](obj: T) -> T:
    """Wrap vrchatapi API object."""
    return cast(T, _ApiWrapper(obj))


class _ApiWrapper:
    def __init__(self, obj):
        self._obj = obj

    @lru_cache(maxsize=32)
    def __getattr__(self, name):
        # Retrieve the attribute from the original object
        attr = getattr(self._obj, name)

        raw_data_method = getattr(self._obj, f"{name}_with_http_info", None)

        # Only generated API endpoint methods have a raw-response counterpart.
        if callable(attr) and callable(raw_data_method):

            @wraps(attr)
            async def async_func(*args, **kwargs):
                api_response = await raw_data_method(*args, **kwargs)
                return json.loads(api_response.raw_data)

            return async_func

        return attr
