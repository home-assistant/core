"""WebSocket API for the Marketplace."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..base import async_get_marketplace
from .critical import marketplace_critical_acknowledge, marketplace_critical_list
from .repositories import (
    marketplace_repositories_add,
    marketplace_repositories_clear_new,
    marketplace_repositories_list,
    marketplace_repositories_remove,
    marketplace_repositories_removed,
)
from .repository import (
    marketplace_repository_beta,
    marketplace_repository_download,
    marketplace_repository_ignore,
    marketplace_repository_info,
    marketplace_repository_refresh,
    marketplace_repository_release_notes,
    marketplace_repository_releases,
    marketplace_repository_remove,
    marketplace_repository_state,
    marketplace_repository_version,
)


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """WebSocket API for the Marketplace."""
    websocket_api.async_register_command(hass, marketplace_info)
    websocket_api.async_register_command(hass, marketplace_subscribe)

    websocket_api.async_register_command(hass, marketplace_repository_info)
    websocket_api.async_register_command(hass, marketplace_repository_download)
    websocket_api.async_register_command(hass, marketplace_repository_ignore)
    websocket_api.async_register_command(hass, marketplace_repository_state)
    websocket_api.async_register_command(hass, marketplace_repository_version)
    websocket_api.async_register_command(hass, marketplace_repository_beta)
    websocket_api.async_register_command(hass, marketplace_repository_refresh)
    websocket_api.async_register_command(hass, marketplace_repository_release_notes)
    websocket_api.async_register_command(hass, marketplace_repository_remove)

    websocket_api.async_register_command(hass, marketplace_critical_acknowledge)
    websocket_api.async_register_command(hass, marketplace_critical_list)

    websocket_api.async_register_command(hass, marketplace_repositories_list)
    websocket_api.async_register_command(hass, marketplace_repositories_add)
    websocket_api.async_register_command(hass, marketplace_repositories_clear_new)
    websocket_api.async_register_command(hass, marketplace_repositories_removed)
    websocket_api.async_register_command(hass, marketplace_repositories_remove)
    websocket_api.async_register_command(hass, marketplace_repository_releases)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "marketplace/subscribe",
        vol.Required("signal"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def marketplace_subscribe(
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
async def marketplace_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return information about the Marketplace."""
    marketplace = async_get_marketplace(hass)
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "categories": marketplace.common.categories,
                "country": marketplace.configuration.country,
                "debug": marketplace.configuration.debug,
                "disabled_reason": marketplace.system.disabled_reason,
                "has_pending_tasks": marketplace.queue.has_pending_tasks,
                "lovelace_mode": marketplace.core.lovelace_mode,
                "stage": marketplace.stage,
                "startup": marketplace.status.startup,
                "version": marketplace.version,
            },
        )
    )
