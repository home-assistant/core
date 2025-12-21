"""API for persistent storage for the frontend."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

DATA_STORAGE: HassKey[dict[str, asyncio.Future[UserStore]]] = HassKey(
    "frontend_storage"
)
DATA_SYSTEM_STORAGE: HassKey[SystemStore] = HassKey("frontend_system_storage")
STORAGE_VERSION_USER_DATA = 1
STORAGE_VERSION_SYSTEM_DATA = 1


async def async_setup_frontend_storage(hass: HomeAssistant) -> None:
    """Set up frontend storage."""
    websocket_api.async_register_command(hass, websocket_set_user_data)
    websocket_api.async_register_command(hass, websocket_get_user_data)
    websocket_api.async_register_command(hass, websocket_subscribe_user_data)
    websocket_api.async_register_command(hass, websocket_set_system_data)
    websocket_api.async_register_command(hass, websocket_get_system_data)
    websocket_api.async_register_command(hass, websocket_subscribe_system_data)


async def async_user_store(hass: HomeAssistant, user_id: str) -> UserStore:
    """Access a user store."""
    stores = hass.data.setdefault(DATA_STORAGE, {})
    if (future := stores.get(user_id)) is None:
        future = stores[user_id] = hass.loop.create_future()
        store = UserStore(hass, user_id)
        try:
            await store.async_load()
        except BaseException as ex:
            del stores[user_id]
            future.set_exception(ex)
            raise
        future.set_result(store)

    return await future


class UserStore:
    """User store for frontend data."""

    def __init__(self, hass: HomeAssistant, user_id: str) -> None:
        """Initialize the user store."""
        self._store = _UserStore(hass, user_id)
        self.data: dict[str, Any] = {}
        self.subscriptions: dict[str | None, list[Callable[[], None]]] = {}

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


@singleton.singleton(DATA_SYSTEM_STORAGE, async_=True)
async def async_system_store(hass: HomeAssistant) -> SystemStore:
    """Access the system store."""
    store = SystemStore(hass)
    await store.async_load()
    return store


class SystemStore:
    """System store for frontend data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the system store."""
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION_SYSTEM_DATA,
            "frontend.system_data",
        )
        self.data: dict[str, Any] = {}
        self.subscriptions: dict[str, list[Callable[[], None]]] = {}

    async def async_load(self) -> None:
        """Load the data from the store."""
        self.data = await self._store.async_load() or {}

    async def async_set_item(self, key: str, value: Any) -> None:
        """Set an item and save the store."""
        self.data[key] = value
        self._store.async_delay_save(lambda: self.data, 1.0)
        for cb in self.subscriptions.get(key, []):
            cb()

    @callback
    def async_subscribe(
        self, key: str, on_update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Subscribe to store updates."""
        self.subscriptions.setdefault(key, []).append(on_update_callback)

        def unsubscribe() -> None:
            """Unsubscribe from the store."""
            self.subscriptions[key].remove(on_update_callback)

        return unsubscribe


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


def with_system_store(
    orig_func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], SystemStore],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate function to provide system store."""

    @wraps(orig_func)
    async def with_system_store_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide system store to function."""
        store = await async_system_store(hass)

        await orig_func(hass, connection, msg, store)

    return with_system_store_func


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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "frontend/set_system_data",
        vol.Required("key"): str,
        vol.Required("value"): vol.Any(bool, str, int, float, dict, list, None),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@with_system_store
async def websocket_set_system_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: SystemStore,
) -> None:
    """Handle set system data command."""
    await store.async_set_item(msg["key"], msg["value"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "frontend/get_system_data", vol.Required("key"): str}
)
@websocket_api.async_response
@with_system_store
async def websocket_get_system_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: SystemStore,
) -> None:
    """Handle get system data command."""
    connection.send_result(msg["id"], {"value": store.data.get(msg["key"])})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "frontend/subscribe_system_data",
        vol.Required("key"): str,
    }
)
@websocket_api.async_response
@with_system_store
async def websocket_subscribe_system_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: SystemStore,
) -> None:
    """Handle subscribe to system data command."""
    key: str = msg["key"]

    def on_data_update() -> None:
        """Handle system data update."""
        connection.send_event(msg["id"], {"value": store.data.get(key)})

    connection.subscriptions[msg["id"]] = store.async_subscribe(key, on_data_update)
    on_data_update()
    connection.send_result(msg["id"])
