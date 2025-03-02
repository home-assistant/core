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

DATA_STORAGE = "frontend_storage"
STORAGE_VERSION_USER_DATA = 1


@callback
def _initialize_frontend_storage(hass: HomeAssistant) -> None:
    """Set up frontend storage."""
    if DATA_STORAGE in hass.data:
        return
    hass.data[DATA_STORAGE] = ({}, {})


async def async_setup_frontend_storage(hass: HomeAssistant) -> None:
    """Set up frontend storage."""
    _initialize_frontend_storage(hass)
    websocket_api.async_register_command(hass, websocket_set_user_data)
    websocket_api.async_register_command(hass, websocket_get_user_data)


async def async_user_store(
    hass: HomeAssistant, user_id: str
) -> tuple[Store, dict[str, Any]]:
    """Access a user store."""
    _initialize_frontend_storage(hass)
    stores, data = hass.data[DATA_STORAGE]
    if (store := stores.get(user_id)) is None:
        store = stores[user_id] = Store(
            hass,
            STORAGE_VERSION_USER_DATA,
            f"frontend.user_data_{user_id}",
        )

    if user_id not in data:
        data[user_id] = await store.async_load() or {}

    return store, data[user_id]


def with_store(
    orig_func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], Store, dict[str, Any]],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate function to provide data."""

    @wraps(orig_func)
    async def with_store_func(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide user specific data and store to function."""
        user_id = connection.user.id

        store, user_data = await async_user_store(hass, user_id)

        await orig_func(hass, connection, msg, store, user_data)

    return with_store_func


@websocket_api.websocket_command(
    {
        vol.Required("type"): "frontend/set_user_data",
        vol.Required("key"): str,
        vol.Required("value"): vol.Any(bool, str, int, float, dict, list, None),
    }
)
@websocket_api.async_response
@with_store
async def websocket_set_user_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: Store,
    data: dict[str, Any],
) -> None:
    """Handle set global data command.

    Async friendly.
    """
    data[msg["key"]] = msg["value"]
    await store.async_save(data)
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {vol.Required("type"): "frontend/get_user_data", vol.Optional("key"): str}
)
@websocket_api.async_response
@with_store
async def websocket_get_user_data(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    store: Store,
    data: dict[str, Any],
) -> None:
    """Handle get global data command.

    Async friendly.
    """
    connection.send_message(
        websocket_api.result_message(
            msg["id"], {"value": data.get(msg["key"]) if "key" in msg else data}
        )
    )
