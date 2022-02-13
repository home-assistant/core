"""Websocket commands for the Backup integration."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .manager import BackupManager


@callback
def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_create)
    websocket_api.async_register_command(hass, handle_remove)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """List all stored backups."""
    manager: BackupManager = hass.data[DOMAIN]

    if not manager.backups:
        await hass.async_add_executor_job(manager.load_backups)

    connection.send_result(
        msg["id"],
        {
            "backups": list(manager.backups),
            "backing_up": manager.backing_up,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/remove",
        vol.Required("slug"): str,
    }
)
@websocket_api.async_response
async def handle_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """Remove a backup."""
    manager: BackupManager = hass.data[DOMAIN]

    await hass.async_add_executor_job(manager.remove_backup, msg["slug"])

    connection.send_message(websocket_api.result_message(msg["id"]))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/generate"})
@websocket_api.async_response
async def handle_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
):
    """Generate a backup."""
    manager: BackupManager = hass.data[DOMAIN]
    backup = await manager.generate_backup()
    connection.send_message(websocket_api.result_message(msg["id"], backup))
