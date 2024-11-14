"""Websocket commands for the Backup integration."""

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DATA_MANAGER, LOGGER
from .manager import BackupProgress


@callback
def async_register_websocket_handlers(hass: HomeAssistant, with_hassio: bool) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, backup_agents_download)
    websocket_api.async_register_command(hass, backup_agents_info)
    websocket_api.async_register_command(hass, backup_agents_list_backups)

    if with_hassio:
        websocket_api.async_register_command(hass, handle_backup_end)
        websocket_api.async_register_command(hass, handle_backup_start)
        websocket_api.async_register_command(hass, handle_backup_upload)
        return

    websocket_api.async_register_command(hass, handle_details)
    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_create)
    websocket_api.async_register_command(hass, handle_remove)
    websocket_api.async_register_command(hass, handle_restore)


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
            "backing_up": manager.backup_task is not None,
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
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/restore",
        vol.Required("slug"): str,
    }
)
@websocket_api.async_response
async def handle_restore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a backup."""
    await hass.data[DATA_MANAGER].async_restore_backup(msg["slug"])
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/generate",
        vol.Optional("addons_included"): [str],
        vol.Optional("database_included", default=True): bool,
        vol.Optional("folders_included"): [str],
        vol.Optional("name"): str,
    }
)
@websocket_api.async_response
async def handle_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a backup."""

    def on_progress(progress: BackupProgress) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], progress))

    backup = await hass.data[DATA_MANAGER].async_create_backup(
        addons_included=msg.get("addons_included"),
        database_included=msg["database_included"],
        folders_included=msg.get("folders_included"),
        name=msg.get("name"),
        on_progress=on_progress,
    )
    connection.send_result(msg["id"], backup)


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
        vol.Required("type"): "backup/upload",
        vol.Required("data"): {
            vol.Required("slug"): str,
        },
    }
)
@websocket_api.async_response
async def handle_backup_upload(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Backup upload."""
    LOGGER.debug("Backup upload notification")
    data = msg["data"]

    try:
        await hass.data[DATA_MANAGER].async_upload_backup(slug=data["slug"])
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "backup_upload_failed", str(err))
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
            "agents": [{"agent_id": agent_id} for agent_id in manager.backup_agents],
            "syncing": manager.syncing,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/agents/list_backups"})
@websocket_api.async_response
async def backup_agents_list_backups(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a list of uploaded backups."""
    manager = hass.data[DATA_MANAGER]
    backups: list[dict[str, Any]] = []
    await manager.load_platforms()
    for agent_id, agent in manager.backup_agents.items():
        _listed_backups = await agent.async_list_backups()
        backups.extend({**b.as_dict(), "agent_id": agent_id} for b in _listed_backups)
    connection.send_result(msg["id"], backups)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/agents/download",
        vol.Required("agent_id"): str,
        vol.Required("backup_id"): str,
        vol.Required("slug"): str,
    }
)
@websocket_api.async_response
async def backup_agents_download(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Download an uploaded backup."""
    manager = hass.data[DATA_MANAGER]
    await manager.load_platforms()

    if not (agent := manager.backup_agents.get(msg["agent_id"])):
        connection.send_error(
            msg["id"], "unknown_agent", f"Agent {msg['agent_id']} not found"
        )
        return
    try:
        await agent.async_download_backup(
            id=msg["backup_id"],
            path=Path(hass.config.path("backup"), f"{msg['slug']}.tar"),
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "backup_agents_download", str(err))
        return

    connection.send_result(msg["id"])
