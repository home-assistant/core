"""WebSocket API for the HTTP integration user config."""

from typing import Any, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant

from .storage import async_get_store, to_stored


def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the HTTP config WebSocket commands.

    The core ``homeassistant.components.websocket_api`` dependency is imported
    lazily because it imports from ``homeassistant.components.http``; using its
    decorators at this module's load time would create a circular import.
    """
    from homeassistant.components import websocket_api  # noqa: PLC0415

    @websocket_api.require_admin
    @websocket_api.websocket_command({vol.Required("type"): "http/config/get"})
    @websocket_api.async_response
    async def ws_get_config(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Return the current user-managed HTTP config."""
        store = async_get_store(hass)
        stored = await store.async_load() or {}
        connection.send_result(msg["id"], {"config": stored})

    @websocket_api.require_admin
    @websocket_api.websocket_command(
        {
            vol.Required("type"): "http/config/update",
            vol.Required("config"): dict,
        }
    )
    @websocket_api.async_response
    async def ws_update_config(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Merge the incoming patch into the stored HTTP config and save."""
        # Local import: HTTP_SCHEMA lives in __init__.py, which already imports
        # this module to wire up the commands.
        from . import HTTP_SCHEMA  # noqa: PLC0415

        store = async_get_store(hass)
        existing = await store.async_load() or {}
        merged = {**existing, **msg["config"]}

        try:
            validated = HTTP_SCHEMA(merged)
        except vol.Invalid as err:
            connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
            return

        stored = to_stored(cast(dict[str, Any], validated))
        await store.async_save(stored)
        connection.send_result(msg["id"], {"config": stored})

    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_update_config)
