"""Data store for the VRChat integration."""

from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api_data_types import CurrentUser
from .const import DOMAIN


class VRChatConfigData(TypedDict, total=False):
    """VRChat credentials stored in a config entry."""

    username: str
    password: str


class VRChatAuthCookie(TypedDict, total=False):
    """VRChat auth cookie."""

    auth: str
    twoFactorAuth: str


VRChatAuthCookieStore: dict[str, Store[VRChatAuthCookie]] = {}


def get_vrchat_auth_cookie_store(hass: HomeAssistant, user_id: str):
    """Get an auth cookie store for given user id."""
    store = VRChatAuthCookieStore.get(user_id)
    if store is None:
        store = Store[VRChatAuthCookie](hass, 1, f"{DOMAIN}.{user_id}")
        VRChatAuthCookieStore[user_id] = store
    return store


InitialCurrentUserData: dict[str, CurrentUser] = {}
