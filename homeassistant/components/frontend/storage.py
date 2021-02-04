"""API for persistent storage for the frontend."""
from functools import wraps

import voluptuous as vol

from homeassistant.components import websocket_api

# mypy: allow-untyped-calls, allow-untyped-defs

DATA_STORAGE = "frontend_storage"
STORAGE_VERSION_USER_DATA = 1


async def async_setup_frontend_storage(hass):
    """Set up frontend storage."""
    hass.data[DATA_STORAGE] = ({}, {})
    hass.components.websocket_api.async_register_command(websocket_set_user_data)
    hass.components.websocket_api.async_register_command(websocket_get_user_data)


def with_store(orig_func):
    """Decorate function to provide data."""

    @wraps(orig_func)
    async def with_store_func(hass, connection, msg):
        """Provide user specific data and store to function."""
        stores, data = hass.data[DATA_STORAGE]
        user_id = connection.user.id
        store = stores.get(user_id)

        if store is None:
            store = stores[user_id] = hass.helpers.storage.Store(
                STORAGE_VERSION_USER_DATA, f"frontend.user_data_{connection.user.id}"
            )

        if user_id not in data:
            data[user_id] = await store.async_load() or {}

        await orig_func(hass, connection, msg, store, data[user_id])

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
async def websocket_set_user_data(hass, connection, msg, store, data):
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
async def websocket_get_user_data(hass, connection, msg, store, data):
    """Handle get global data command.

    Async friendly.
    """
    connection.send_message(
        websocket_api.result_message(
            msg["id"], {"value": data.get(msg["key"]) if "key" in msg else data}
        )
    )
