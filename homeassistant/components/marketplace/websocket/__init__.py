"""WebSocket API for the Marketplace."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ..base import MarketplaceManager
from ..const import DOMAIN
from .critical import marketplace_critical_acknowledge, marketplace_critical_list
from .decorators import marketplace_command
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
    websocket_api.async_register_command(hass, marketplace_github_connect)
    websocket_api.async_register_command(hass, marketplace_subscribe)
    websocket_api.async_register_command(hass, marketplace_warning_accept)

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
        probatio.Required("type"): "marketplace/subscribe",
        probatio.Required("signal"): str,
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
        probatio.Required("type"): "marketplace/info",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Return information about the Marketplace."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            {
                "categories": marketplace.common.categories,
                "debug": marketplace.configuration.debug,
                "disabled_reason": marketplace.system.disabled_reason,
                "github_connected": marketplace.github_connected,
                "has_pending_tasks": marketplace.queue.has_pending_tasks,
                "lovelace_mode": marketplace.core.lovelace_mode,
                "stage": marketplace.stage,
                "startup": marketplace.status.startup,
                "version": marketplace.version,
                "warning_accepted": marketplace.warning_accepted(connection.user.id),
                "warning_reminder_due": marketplace.warning_reminder_due(
                    connection.user.id
                ),
            },
        )
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/github/connect",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_github_connect(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Start the flow that connects a GitHub account to the Marketplace."""
    config_entry = marketplace.configuration.config_entry
    assert config_entry is not None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": config_entry.entry_id},
    )
    connection.send_message(
        websocket_api.result_message(msg["id"], {"flow_id": result["flow_id"]})
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/warning/accept",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@marketplace_command()
async def marketplace_warning_accept(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    marketplace: MarketplaceManager,
) -> None:
    """Store that the user read and accepted the first-run warning."""
    marketplace.async_accept_warning(connection.user.id)
    connection.send_message(websocket_api.result_message(msg["id"]))
