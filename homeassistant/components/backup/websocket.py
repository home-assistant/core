"""Websocket commands for the Backup integration."""

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
        return

    websocket_api.async_register_command(hass, handle_details)
    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_create)
    websocket_api.async_register_command(hass, handle_delete)
    websocket_api.async_register_command(hass, handle_restore)

    websocket_api.async_register_command(hass, handle_config_info)
    websocket_api.async_register_command(hass, handle_config_update)


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
    backups, agent_errors = await manager.async_get_backups()
    connection.send_result(
        msg["id"],
        {
            "agent_errors": {
                agent_id: str(err) for agent_id, err in agent_errors.items()
            },
            "backups": [b.as_dict() for b in backups.values()],
            "backing_up": manager.backup_task is not None,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/details",
        vol.Required("backup_id"): str,
    }
)
@websocket_api.async_response
async def handle_details(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get backup details for a specific backup."""
    backup, agent_errors = await hass.data[DATA_MANAGER].async_get_backup(
        msg["backup_id"]
    )
    connection.send_result(
        msg["id"],
        {
            "agent_errors": {
                agent_id: str(err) for agent_id, err in agent_errors.items()
            },
            "backup": backup,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/delete",
        vol.Required("backup_id"): str,
    }
)
@websocket_api.async_response
async def handle_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a backup."""
    await hass.data[DATA_MANAGER].async_delete_backup(msg["backup_id"])
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/restore",
        vol.Required("backup_id"): str,
        vol.Required("agent_id"): str,
        vol.Optional("password"): str,
    }
)
@websocket_api.async_response
async def handle_restore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a backup."""
    await hass.data[DATA_MANAGER].async_restore_backup(
        msg["backup_id"],
        agent_id=msg["agent_id"],
        password=msg.get("password"),
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/generate",
        vol.Optional("addons_included"): [str],
        vol.Required("agent_ids"): [str],
        vol.Optional("database_included", default=True): bool,
        vol.Optional("folders_included"): [str],
        vol.Optional("name"): str,
        vol.Optional("password"): str,
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
        agent_ids=msg["agent_ids"],
        database_included=msg["database_included"],
        folders_included=msg.get("folders_included"),
        name=msg.get("name"),
        on_progress=on_progress,
        password=msg.get("password"),
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
    if not (agent := manager.backup_agents.get(msg["agent_id"])):
        connection.send_error(
            msg["id"], "unknown_agent", f"Agent {msg['agent_id']} not found"
        )
        return
    try:
        path = manager.temp_backup_dir / f"{msg["backup_id"]}.tar"
        await agent.async_download_backup(
            msg["backup_id"],
            path=path,
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "backup_agents_download", str(err))
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "backup/config/info"})
@websocket_api.async_response
async def handle_config_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send the stored backup config."""
    manager = hass.data[DATA_MANAGER]
    connection.send_result(
        msg["id"],
        {
            "config": manager.config.data,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/config/update",
        vol.Optional("max_copies"): int,
    }
)
@websocket_api.async_response
async def handle_config_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update the stored backup config."""
    manager = hass.data[DATA_MANAGER]
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    await manager.config.update(**changes)
    connection.send_result(msg["id"])
