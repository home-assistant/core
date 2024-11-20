"""The Backup integration."""

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.typing import ConfigType

from .agent import BackupAgent, BackupAgentPlatformProtocol, LocalBackupAgent
from .const import DATA_MANAGER, DOMAIN
from .http import async_register_http_views
from .manager import (
    Backup,
    BackupManager,
    BackupPlatformProtocol,
    BackupProgress,
    BackupReaderWriter,
    CoreBackupReaderWriter,
    NewBackup,
)
from .models import AgentBackup
from .websocket import async_register_websocket_handlers

__all__ = [
    "AgentBackup",
    "Backup",
    "BackupAgent",
    "BackupAgentPlatformProtocol",
    "BackupPlatformProtocol",
    "BackupProgress",
    "BackupReaderWriter",
    "LocalBackupAgent",
    "NewBackup",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SERVICE_CREATE_SCHEMA = vol.Schema({vol.Optional(CONF_PASSWORD): str})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Backup integration."""
    with_hassio = is_hassio(hass)

    reader_writer: BackupReaderWriter
    if not with_hassio:
        reader_writer = CoreBackupReaderWriter(hass)
    else:
        # pylint: disable-next=import-outside-toplevel, hass-component-root-import
        from homeassistant.components.hassio.backup import SupervisorBackupReaderWriter

        reader_writer = SupervisorBackupReaderWriter(hass)

    backup_manager = BackupManager(hass, reader_writer)
    hass.data[DATA_MANAGER] = backup_manager
    await backup_manager.async_setup()

    async_register_websocket_handlers(hass, with_hassio)

    async def async_handle_create_service(call: ServiceCall) -> None:
        """Service handler for creating backups."""
        agent_id = list(backup_manager.local_backup_agents)[0]
        await backup_manager.async_create_backup(
            addons_included=None,
            agent_ids=[agent_id],
            database_included=True,
            folders_included=None,
            name=None,
            on_progress=None,
            password=call.data.get(CONF_PASSWORD),
        )
        if backup_task := backup_manager.backup_task:
            await backup_task

    hass.services.async_register(
        DOMAIN,
        "create",
        async_handle_create_service,
        schema=SERVICE_CREATE_SCHEMA,
    )

    async_register_http_views(hass)

    return True
