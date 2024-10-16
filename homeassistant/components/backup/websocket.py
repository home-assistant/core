"""Websocket commands for the Backup integration."""

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DATA_MANAGER, LOGGER
from .models import BaseBackup


@callback
def async_register_websocket_handlers(hass: HomeAssistant, with_hassio: bool) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, backup_agents_download)
    websocket_api.async_register_command(hass, backup_agents_info)
    websocket_api.async_register_command(hass, backup_agents_list_synced_backups)

    if with_hassio:
        websocket_api.async_register_command(hass, handle_backup_end)
        websocket_api.async_register_command(hass, handle_backup_start)
        websocket_api.async_register_command(hass, handle_backup_sync)
        return

    websocket_api.async_register_command(hass, handle_details)
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
    manager = hass.data[DATA_MANAGER]
    backups = await manager.async_get_backups()
    connection.send_result(
        msg["id"],
        {
            "backups": [b.as_dict() for b in backups.values()],
            "backing_up": manager.backing_up,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/details",
        vol.Required("slug"): str,
    }
)
@websocket_api.async_response
async def handle_details(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get backup details for a specific slug."""
    backup = await hass.data[DATA_MANAGER].async_get_backup(slug=msg["slug"])
    connection.send_result(
        msg["id"],
        {
            "backup": backup,
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
    await hass.data[DATA_MANAGER].async_remove_backup(slug=msg["slug"])
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
    manager = hass.data[DATA_MANAGER]
    backup = await manager.async_create_backup()
    connection.send_result(msg["id"], backup)
    await manager.async_sync_backup(backup=backup)


@websocket_api.ws_require_user(only_supervisor=True)
@websocket_api.websocket_command({vol.Required("type"): "backup/start"})
@websocket_api.async_response
async def handle_backup_start(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Backup start notification."""
    manager = hass.data[DATA_MANAGER]
    manager.backing_up = True
    LOGGER.debug("Backup start notification")

    try:
        await manager.async_pre_backup_actions()
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
    manager = hass.data[DATA_MANAGER]
    manager.backing_up = False
    LOGGER.debug("Backup end notification")

    try:
        await manager.async_post_backup_actions()
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "post_backup_actions_failed", str(err))
        return

    connection.send_result(msg["id"])


@websocket_api.ws_require_user(only_supervisor=True)
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/sync",
        vol.Required("backup"): {
            vol.Required("date"): str,
            vol.Required("name"): str,
            vol.Required("size"): float,
            vol.Required("slug"): str,
        },
    }
)
@websocket_api.async_response
async def handle_backup_sync(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Backup sync notification."""
    LOGGER.debug("Backup sync notification")
    backup = msg["backup"]

    try:
        await hass.data[DATA_MANAGER].async_sync_backup(
            backup=BaseBackup(
                date=backup["date"],
                name=backup["name"],
                size=backup["size"],
                slug=backup["slug"],
            )
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "backup_sync_failed", str(err))
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
    """Return backup agents info."""
    manager = hass.data[DATA_MANAGER]
    await manager.load_platforms()
    connection.send_result(
        msg["id"],
        {
            "agents": [{"id": agent_id} for agent_id in manager.sync_agents],
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
    manager = hass.data[DATA_MANAGER]
    backups: list[dict[str, Any]] = []
    await manager.load_platforms()
    for agent_id, agent in manager.sync_agents.items():
        _listed_backups = await agent.async_list_backups()
        backups.extend({**b.as_dict(), "agent_id": agent_id} for b in _listed_backups)
    connection.send_result(msg["id"], backups)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/agents/download",
        vol.Required("agent"): str,
        vol.Required("sync_id"): str,
        vol.Required("slug"): str,
    }
)
@websocket_api.async_response
async def backup_agents_download(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Download a synced backup."""
    manager = hass.data[DATA_MANAGER]
    await manager.load_platforms()

    if not (agent := manager.sync_agents.get(msg["agent"])):
        connection.send_error(
            msg["id"], "unknown_agent", f"Agent {msg['agent']} not found"
        )
        return
    try:
        await agent.async_download_backup(
            id=msg["sync_id"],
            path=Path(hass.config.path("backup"), f"{msg['slug']}.tar"),
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "backup_agents_download", str(err))
        return

    connection.send_result(msg["id"])
