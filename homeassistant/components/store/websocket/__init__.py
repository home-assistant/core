"""Register_commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import voluptuous as vol

from ..const import DOMAIN
from .critical import hacs_critical_acknowledge, hacs_critical_list
from .repositories import (
    hacs_repositories_add,
    hacs_repositories_clear_new,
    hacs_repositories_list,
    hacs_repositories_remove,
    hacs_repositories_removed,
)
from .repository import (
    hacs_repository_beta,
    hacs_repository_download,
    hacs_repository_ignore,
    hacs_repository_info,
    hacs_repository_refresh,
    hacs_repository_release_notes,
    hacs_repository_releases,
    hacs_repository_remove,
    hacs_repository_state,
    hacs_repository_version,
)

if TYPE_CHECKING:
    from ..base import HacsBase


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register_commands."""
    websocket_api.async_register_command(hass, hacs_info)
    websocket_api.async_register_command(hass, hacs_subscribe)

    websocket_api.async_register_command(hass, hacs_repository_info)
    websocket_api.async_register_command(hass, hacs_repository_download)
    websocket_api.async_register_command(hass, hacs_repository_ignore)
    websocket_api.async_register_command(hass, hacs_repository_state)
    websocket_api.async_register_command(hass, hacs_repository_version)
    websocket_api.async_register_command(hass, hacs_repository_beta)
    websocket_api.async_register_command(hass, hacs_repository_refresh)
    websocket_api.async_register_command(hass, hacs_repository_release_notes)
    websocket_api.async_register_command(hass, hacs_repository_remove)

    websocket_api.async_register_command(hass, hacs_critical_acknowledge)
    websocket_api.async_register_command(hass, hacs_critical_list)

    websocket_api.async_register_command(hass, hacs_repositories_list)
    websocket_api.async_register_command(hass, hacs_repositories_add)
    websocket_api.async_register_command(hass, hacs_repositories_clear_new)
    websocket_api.async_register_command(hass, hacs_repositories_removed)
    websocket_api.async_register_command(hass, hacs_repositories_remove)
    websocket_api.async_register_command(hass, hacs_repository_releases)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hacs/subscribe",
        vol.Required("signal"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_subscribe(
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
        vol.Required("type"): "hacs/info",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def hacs_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return information about HACS."""
    hacs: HacsBase = hass.data.get(DOMAIN)
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "categories": hacs.common.categories,
                "country": hacs.configuration.country,
                "debug": hacs.configuration.debug,
                "dev": hacs.configuration.dev,
                "disabled_reason": hacs.system.disabled_reason,
                "has_pending_tasks": hacs.queue.has_pending_tasks,
                "lovelace_mode": hacs.core.lovelace_mode,
                "stage": hacs.stage,
                "startup": hacs.status.startup,
                "version": hacs.version,
            },
        )
    )
