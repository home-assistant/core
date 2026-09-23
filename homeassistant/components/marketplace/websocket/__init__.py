"""WebSocket API for the Marketplace."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..base import async_get_store
from .critical import store_critical_acknowledge, store_critical_list
from .repositories import (
    store_repositories_add,
    store_repositories_clear_new,
    store_repositories_list,
    store_repositories_remove,
    store_repositories_removed,
)
from .repository import (
    store_repository_beta,
    store_repository_download,
    store_repository_ignore,
    store_repository_info,
    store_repository_refresh,
    store_repository_release_notes,
    store_repository_releases,
    store_repository_remove,
    store_repository_state,
    store_repository_version,
)


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """WebSocket API for the Marketplace."""
    websocket_api.async_register_command(hass, store_info)
    websocket_api.async_register_command(hass, store_subscribe)

    websocket_api.async_register_command(hass, store_repository_info)
    websocket_api.async_register_command(hass, store_repository_download)
    websocket_api.async_register_command(hass, store_repository_ignore)
    websocket_api.async_register_command(hass, store_repository_state)
    websocket_api.async_register_command(hass, store_repository_version)
    websocket_api.async_register_command(hass, store_repository_beta)
    websocket_api.async_register_command(hass, store_repository_refresh)
    websocket_api.async_register_command(hass, store_repository_release_notes)
    websocket_api.async_register_command(hass, store_repository_remove)

    websocket_api.async_register_command(hass, store_critical_acknowledge)
    websocket_api.async_register_command(hass, store_critical_list)

    websocket_api.async_register_command(hass, store_repositories_list)
    websocket_api.async_register_command(hass, store_repositories_add)
    websocket_api.async_register_command(hass, store_repositories_clear_new)
    websocket_api.async_register_command(hass, store_repositories_removed)
    websocket_api.async_register_command(hass, store_repositories_remove)
    websocket_api.async_register_command(hass, store_repository_releases)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/subscribe",
        vol.Required("signal"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle websocket subscriptions."""

    @callback
    def forward_messages(data: dict | None = None) -> None:
        """Forward events to websocket."""
        connection.send_message(websocket_api.event_message(msg["id"], data))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass,
        msg["signal"],
        forward_messages,
    )
    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/info",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return information about the Marketplace."""
    store = async_get_store(hass)
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "categories": store.common.categories,
                "country": store.configuration.country,
                "debug": store.configuration.debug,
                "disabled_reason": store.system.disabled_reason,
                "has_pending_tasks": store.queue.has_pending_tasks,
                "lovelace_mode": store.core.lovelace_mode,
                "stage": store.stage,
                "startup": store.status.startup,
                "version": store.version,
            },
        )
    )
