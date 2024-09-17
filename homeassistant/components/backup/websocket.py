"""Websocket commands for the Backup integration."""

import asyncio
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, LOGGER
from .manager import BackupManager


@callback
def async_register_websocket_handlers(hass: HomeAssistant, with_hassio: bool) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, backup_agents_download)
    websocket_api.async_register_command(hass, backup_agents_info)
    websocket_api.async_register_command(hass, backup_agents_list_synced_backups)

    if with_hassio:
        websocket_api.async_register_command(hass, handle_backup_end)
        websocket_api.async_register_command(hass, handle_backup_start)
        return

    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_create)
    websocket_api.async_register_command(hass, handle_remove)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/info"})
@websocket_api.async_response
async def handle_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List all stored backups."""
    manager: BackupManager = hass.data[DOMAIN]
    backups = await manager.get_backups()
    connection.send_result(
        msg["id"],
        {
            "backups": list(backups.values()),
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
    msg: dict[str, Any],
) -> None:
    """Remove a backup."""
    manager: BackupManager = hass.data[DOMAIN]
    await manager.remove_backup(msg["slug"])
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/generate"})
@websocket_api.async_response
async def handle_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a backup."""
    manager: BackupManager = hass.data[DOMAIN]
    backup = await manager.generate_backup()
    connection.send_result(msg["id"], backup)
    await manager.sync_backup(backup=backup)


@websocket_api.ws_require_user(only_supervisor=True)
@websocket_api.websocket_command({vol.Required("type"): "backup/start"})
@websocket_api.async_response
async def handle_backup_start(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Backup start notification."""
    manager: BackupManager = hass.data[DOMAIN]
    manager.backing_up = True
    LOGGER.debug("Backup start notification")

    try:
        await manager.pre_backup_actions()
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "pre_backup_actions_failed", str(err))
        return

    connection.send_result(msg["id"])


@websocket_api.ws_require_user(only_supervisor=True)
@websocket_api.websocket_command({vol.Required("type"): "backup/end"})
@websocket_api.async_response
async def handle_backup_end(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Backup end notification."""
    manager: BackupManager = hass.data[DOMAIN]
    manager.backing_up = False
    LOGGER.debug("Backup end notification")

    try:
        await manager.post_backup_actions()
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "post_backup_actions_failed", str(err))
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/agents/info"})
@websocket_api.async_response
async def backup_agents_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Backup agents info."""
    manager: BackupManager = hass.data[DOMAIN]
    await manager.load_platforms()
    connection.send_result(
        msg["id"],
        {
            "agents": list(manager.sync_agents),
            "syncing": manager.syncing,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/agents/synced"})
@websocket_api.async_response
async def backup_agents_list_synced_backups(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a list of synced backups."""
    manager: BackupManager = hass.data[DOMAIN]
    await manager.load_platforms()
    backups = await asyncio.gather(
        *[agent.async_list_backups() for agent in manager.sync_agents.values()]
    )
    connection.send_result(msg["id"], [b.as_dict() for bl in backups for b in bl])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/agents/download",
        vol.Required("agent"): str,
        vol.Required("sync_id"): str,
    }
)
@websocket_api.async_response
async def backup_agents_download(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Download a synced backup."""
    manager: BackupManager = hass.data[DOMAIN]
    await manager.load_platforms()

    if not (agent := manager.sync_agents.get(msg["agent"])):
        connection.send_error(
            msg["id"], "unknown_agent", f"Agent {msg['agent']} not found"
        )
        return
    try:
        await agent.async_download_backup(
            id=msg["sync_id"], path=Path(hass.config.path("backup"))
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "backup_agents_download", str(err))
        return

    connection.send_result(msg["id"])
