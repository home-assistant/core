"""Websocket commands for the Backup integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .config import Day, ScheduleRecurrence
from .const import DATA_MANAGER, LOGGER
from .manager import DecryptOnDowloadNotSupported, IncorrectPasswordError
from .models import BackupNotFound, Folder


@callback
def async_register_websocket_handlers(hass: HomeAssistant, with_hassio: bool) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, backup_agents_info)

    if with_hassio:
        websocket_api.async_register_command(hass, handle_backup_end)
        websocket_api.async_register_command(hass, handle_backup_start)

    websocket_api.async_register_command(hass, handle_details)
    websocket_api.async_register_command(hass, handle_info)
    websocket_api.async_register_command(hass, handle_can_decrypt_on_download)
    websocket_api.async_register_command(hass, handle_create)
    websocket_api.async_register_command(hass, handle_create_with_automatic_settings)
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
            "backups": list(backups.values()),
            "last_attempted_automatic_backup": manager.config.data.last_attempted_automatic_backup,
            "last_completed_automatic_backup": manager.config.data.last_completed_automatic_backup,
            "last_completed_automatic_backup_id": manager.config.data.last_completed_automatic_backup_id,
            "last_action_event": manager.last_action_event,
            "next_automatic_backup": manager.config.data.schedule.next_automatic_backup,
            "next_automatic_backup_additional": manager.config.data.schedule.next_automatic_backup_additional,
            "state": manager.state,
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
    agent_errors = await hass.data[DATA_MANAGER].async_delete_backup(msg["backup_id"])
    connection.send_result(
        msg["id"],
        {
            "agent_errors": {
                agent_id: str(err) for agent_id, err in agent_errors.items()
            }
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/restore",
        vol.Required("backup_id"): str,
        vol.Required("agent_id"): str,
        vol.Optional("password"): str,
        vol.Optional("restore_addons"): [str],
        vol.Optional("restore_database", default=True): bool,
        vol.Optional("restore_folders"): [vol.Coerce(Folder)],
        vol.Optional("restore_homeassistant", default=True): bool,
    }
)
@websocket_api.async_response
async def handle_restore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a backup."""
    try:
        await hass.data[DATA_MANAGER].async_restore_backup(
            msg["backup_id"],
            agent_id=msg["agent_id"],
            password=msg.get("password"),
            restore_addons=msg.get("restore_addons"),
            restore_database=msg["restore_database"],
            restore_folders=msg.get("restore_folders"),
            restore_homeassistant=msg["restore_homeassistant"],
        )
    except BackupNotFound:
        connection.send_error(msg["id"], "backup_not_found", "Backup not found")
    except IncorrectPasswordError:
        connection.send_error(msg["id"], "password_incorrect", "Incorrect password")
    else:
        connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/can_decrypt_on_download",
        vol.Required("backup_id"): str,
        vol.Required("agent_id"): str,
        vol.Required("password"): str,
    }
)
@websocket_api.async_response
async def handle_can_decrypt_on_download(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Check if the supplied password is correct."""
    try:
        await hass.data[DATA_MANAGER].async_can_decrypt_on_download(
            msg["backup_id"],
            agent_id=msg["agent_id"],
            password=msg.get("password"),
        )
    except BackupNotFound:
        connection.send_error(msg["id"], "backup_not_found", "Backup not found")
    except IncorrectPasswordError:
        connection.send_error(msg["id"], "password_incorrect", "Incorrect password")
    except DecryptOnDowloadNotSupported:
        connection.send_error(
            msg["id"], "decrypt_not_supported", "Decrypt on download not supported"
        )
    else:
        connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/generate",
        vol.Required("agent_ids"): [str],
        vol.Optional("include_addons"): [str],
        vol.Optional("include_all_addons", default=False): bool,
        vol.Optional("include_database", default=True): bool,
        vol.Optional("include_folders"): [vol.Coerce(Folder)],
        vol.Optional("include_homeassistant", default=True): bool,
        vol.Optional("name"): vol.Any(str, None),
        vol.Optional("password"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def handle_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a backup."""

    backup = await hass.data[DATA_MANAGER].async_initiate_backup(
        agent_ids=msg["agent_ids"],
        include_addons=msg.get("include_addons"),
        include_all_addons=msg["include_all_addons"],
        include_database=msg["include_database"],
        include_folders=msg.get("include_folders"),
        include_homeassistant=msg["include_homeassistant"],
        name=msg.get("name"),
        password=msg.get("password"),
    )
    connection.send_result(msg["id"], backup)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/generate_with_automatic_settings",
    }
)
@websocket_api.async_response
async def handle_create_with_automatic_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a backup with stored settings."""

    config_data = hass.data[DATA_MANAGER].config.data
    backup = await hass.data[DATA_MANAGER].async_initiate_backup(
        agent_ids=config_data.create_backup.agent_ids,
        include_addons=config_data.create_backup.include_addons,
        include_all_addons=config_data.create_backup.include_all_addons,
        include_database=config_data.create_backup.include_database,
        include_folders=config_data.create_backup.include_folders,
        include_homeassistant=True,  # always include HA
        name=config_data.create_backup.name,
        password=config_data.create_backup.password,
        with_automatic_settings=True,
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
            "agents": [
                {"agent_id": agent.agent_id, "name": agent.name}
                for agent in manager.backup_agents.values()
            ],
        },
    )


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
    config = manager.config.data.to_dict()
    # Remove state from schedule, it's not needed in the frontend
    # mypy doesn't like deleting from TypedDict, ignore it
    del config["schedule"]["state"]  # type: ignore[misc]
    connection.send_result(
        msg["id"],
        {
            "config": config
            | {
                "next_automatic_backup": manager.config.data.schedule.next_automatic_backup,
                "next_automatic_backup_additional": manager.config.data.schedule.next_automatic_backup_additional,
            }
        },
    )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "backup/config/update",
        vol.Optional("agents"): vol.Schema(
            {
                str: {
                    vol.Optional("protected"): bool,
                    vol.Optional("retention"): vol.Any(
                        vol.Schema(
                            {
                                # Note: We can't use cv.positive_int because it allows 0 even
                                # though 0 is not positive.
                                vol.Optional("copies"): vol.Any(
                                    vol.All(int, vol.Range(min=1)), None
                                ),
                                vol.Optional("days"): vol.Any(
                                    vol.All(int, vol.Range(min=1)), None
                                ),
                            },
                        ),
                        None,
                    ),
                }
            }
        ),
        vol.Optional("automatic_backups_configured"): bool,
        vol.Optional("create_backup"): vol.Schema(
            {
                vol.Optional("agent_ids"): vol.All([str], vol.Unique()),
                vol.Optional("include_addons"): vol.Any(
                    vol.All([str], vol.Unique()), None
                ),
                vol.Optional("include_all_addons"): bool,
                vol.Optional("include_database"): bool,
                vol.Optional("include_folders"): vol.Any(
                    vol.All([vol.Coerce(Folder)], vol.Unique()), None
                ),
                vol.Optional("name"): vol.Any(str, None),
                vol.Optional("password"): vol.Any(str, None),
            },
        ),
        vol.Optional("retention"): vol.Schema(
            {
                # Note: We can't use cv.positive_int because it allows 0 even
                # though 0 is not positive.
                vol.Optional("copies"): vol.Any(vol.All(int, vol.Range(min=1)), None),
                vol.Optional("days"): vol.Any(vol.All(int, vol.Range(min=1)), None),
            },
        ),
        vol.Optional("schedule"): vol.Schema(
            {
                vol.Optional("days"): vol.Any(
                    vol.All([vol.Coerce(Day)], vol.Unique()),
                ),
                vol.Optional("recurrence"): vol.All(
                    str, vol.Coerce(ScheduleRecurrence)
                ),
                vol.Optional("time"): vol.Any(cv.time, None),
            }
        ),
    }
)
def handle_config_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update the stored backup config."""
    manager = hass.data[DATA_MANAGER]
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    manager.config.update(**changes)
    connection.send_result(msg["id"])
