"""WebSocket API for the HTTP integration user config."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.homeassistant import (
    DOMAIN as HASS_DOMAIN,
    SERVICE_HOMEASSISTANT_RESTART,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .config import HTTP_STORAGE_SCHEMA, async_get_and_load_store
from .const import ATTR_CONFIG


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the HTTP config websocket commands."""
    websocket_api.async_register_command(hass, websocket_get_config)
    websocket_api.async_register_command(hass, websocket_set_config)
    websocket_api.async_register_command(hass, websocket_promote_config)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "http/config"})
@websocket_api.async_response
async def websocket_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the HTTP configuration.

    ``stable`` is the confirmed-working config
    ``pending`` is an unconfirmed config awaiting promotion, or ``None``.
    """
    store = await async_get_and_load_store(hass)
    connection.send_result(
        msg["id"],
        {"stable": store.stable, "pending": store.pending},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "http/config/configure",
        vol.Required(ATTR_CONFIG): vol.Any(None, HTTP_STORAGE_SCHEMA),
    }
)
@websocket_api.async_response
async def websocket_set_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Store a new pending HTTP configuration and restart to apply it.

    Restart whenever the pending slot changes, so the runtime config is
    refreshed. The result reports whether a restart was triggered via
    ``{"restart": bool}``.
    """
    store = await async_get_and_load_store(hass)
    previous_pending = store.pending
    await store.async_set_pending(msg[ATTR_CONFIG])
    restart = store.pending != previous_pending
    connection.send_result(msg["id"], {"restart": restart})

    if restart:
        await hass.services.async_call(HASS_DOMAIN, SERVICE_HOMEASSISTANT_RESTART)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "http/config/promote"})
@websocket_api.async_response
async def websocket_promote_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Promote the pending HTTP config to stable.

    Called by the user after they have verified Home Assistant is
    working correctly with the pending config. The stable config is
    the one used by recovery mode, so promotion must be explicit.
    """
    store = await async_get_and_load_store(hass)
    try:
        await store.async_promote_pending()
    except HomeAssistantError as err:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_ALLOWED,
            str(err),
        )
        return

    connection.send_result(msg["id"])
