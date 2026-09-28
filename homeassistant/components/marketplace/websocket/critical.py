"""Register info websocket commands."""

from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv

from ..critical import async_acknowledge_critical_repository
from ..utils.storage import async_load_from_storage

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "marketplace/critical/list",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def marketplace_critical_list(
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
        probatio.Required("type"): "marketplace/critical/acknowledge",
        probatio.Required("repository"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def marketplace_critical_acknowledge(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Acknowledge critical repository."""
    critical = await async_acknowledge_critical_repository(hass, msg["repository"])
    connection.send_message(websocket_api.result_message(msg["id"], critical))
