"""Data store for the VRChat integration."""

from vrchatapi.highlevel.types import CurrentUser, VRChatAuthCookie

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

VRChatAuthCookieStore: dict[str, Store[VRChatAuthCookie]] = {}


def get_vrchat_auth_cookie_store(hass: HomeAssistant, user_id: str):
    """Get an auth cookie store for given user id."""
    store = VRChatAuthCookieStore.get(user_id)
    if store is None:
        store = Store[VRChatAuthCookie](hass, 1, f"{DOMAIN}.{user_id}", private=True)
        VRChatAuthCookieStore[user_id] = store
    return store


InitialCurrentUserData: dict[str, CurrentUser] = {}
