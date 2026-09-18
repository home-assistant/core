"""Register info websocket commands."""

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv

from ..utils.storage import async_load_from_storage, async_save_to_storage

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@websocket_api.websocket_command(
    {
        vol.Required("type"): "store/critical/list",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_critical_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List critical repositories."""
    connection.send_message(
        websocket_api.result_message(
            msg["id"],
            (await async_load_from_storage(hass, "critical") or []),
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "store/critical/acknowledge",
        vol.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def store_critical_acknowledge(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Acknowledge critical repository."""
    repository = msg["repository"]

    critical = await async_load_from_storage(hass, "critical")
    for repo in critical:
        if repository == repo["repository"]:
            repo["acknowledged"] = True
    await async_save_to_storage(hass, "critical", critical)
    connection.send_message(websocket_api.result_message(msg["id"], critical))
