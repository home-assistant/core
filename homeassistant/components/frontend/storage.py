"""API for persistent storage for the frontend."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

DATA_STORAGE: HassKey[dict[str, UserStore]] = HassKey("frontend_storage")
STORAGE_VERSION_USER_DATA = 1


async def async_setup_frontend_storage(hass: HomeAssistant) -> None:
    """Set up frontend storage."""
    websocket_api.async_register_command(hass, websocket_set_user_data)
    websocket_api.async_register_command(hass, websocket_get_user_data)
    websocket_api.async_register_command(hass, websocket_subscribe_user_data)


async def async_user_store(hass: HomeAssistant, user_id: str) -> UserStore:
    """Access a user store."""
    stores = hass.data.setdefault(DATA_STORAGE, {})
    if (store := stores.get(user_id)) is None:
        store = stores[user_id] = UserStore(hass, user_id)
        await store.async_load()

    return store


class UserStore:
    """User store for frontend data."""

    def __init__(self, hass: HomeAssistant, user_id: str) -> None:
        """Initialize the user store."""
        self._store = _UserStore(hass, user_id)
        self.data: dict[str, Any] = {}
        self.subscriptions: dict[str | Any, list[Callable[[], None]]] = {}

    async def async_load(self) -> None:
        """Load the data from the store."""
        self.data = await self._store.async_load() or {}

    async def async_set_item(self, key: str, value: Any) -> None:
        """Set an item item and save the store."""
        self.data[key] = value
        await self._store.async_save(self.data)
        for cb in self.subscriptions.get(None, []):
            cb()
        for cb in self.subscriptions.get(key, []):
            cb()

    @callback
    def async_subscribe(
        self, key: str | None, on_update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Save the data to the store."""
        self.subscriptions.setdefault(key, []).append(on_update_callback)

        def unsubscribe() -> None:
            """Unsubscribe from the store."""
            self.subscriptions[key].remove(on_update_callback)

        return unsubscribe


class _UserStore(Store[dict[str, Any]]):
    """User store for frontend data."""

    def __init__(self, hass: HomeAssistant, user_id: str) -> None:
        """Initialize the user store."""
        super().__init__(
            hass,
            STORAGE_VERSION_USER_DATA,
            f"frontend.user_data_{user_id}",
        )


def with_user_store(
    orig_func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], UserStore],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate function to provide data."""

    @wraps(orig_func)
    async def with_user_store_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide user specific data and store to function."""
        user_id = connection.user.id

        store = await async_user_store(hass, user_id)

        await orig_func(hass, connection, msg, store)

    return with_user_store_func


@websocket_api.websocket_command(
    {
        vol.Required("type"): "frontend/set_user_data",
        vol.Required("key"): str,
        vol.Required("value"): vol.Any(bool, str, int, float, dict, list, None),
    }
)
@websocket_api.async_response
@with_user_store
async def websocket_set_user_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: UserStore,
) -> None:
    """Handle set user data command."""
    await store.async_set_item(msg["key"], msg["value"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "frontend/get_user_data", vol.Optional("key"): str}
)
@websocket_api.async_response
@with_user_store
async def websocket_get_user_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: UserStore,
) -> None:
    """Handle get user data command."""
    data = store.data
    connection.send_result(
        msg["id"], {"value": data.get(msg["key"]) if "key" in msg else data}
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "frontend/subscribe_user_data", vol.Optional("key"): str}
)
@websocket_api.async_response
@with_user_store
async def websocket_subscribe_user_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: UserStore,
) -> None:
    """Handle subscribe to user data command."""
    key: str | None = msg.get("key")

    def on_data_update() -> None:
        """Handle user data update."""
        data = store.data
        connection.send_event(
            msg["id"], {"value": data.get(key) if key is not None else data}
        )

    connection.subscriptions[msg["id"]] = store.async_subscribe(key, on_data_update)
    on_data_update()
    connection.send_result(msg["id"])
