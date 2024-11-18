"""The Backup integration."""

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.typing import ConfigType

from .agent import BackupAgent, BackupAgentPlatformProtocol, UploadedBackup
from .const import DOMAIN, LOGGER
from .http import async_register_http_views
from .manager import Backup, BackupManager, BackupPlatformProtocol
from .models import BackupUploadMetadata, BaseBackup
from .websocket import async_register_websocket_handlers

__all__ = [
    "Backup",
    "BackupAgent",
    "BackupAgentPlatformProtocol",
    "BackupPlatformProtocol",
    "BackupUploadMetadata",
    "BaseBackup",
    "UploadedBackup",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SERVICE_CREATE_SCHEMA = vol.Schema({vol.Optional(CONF_PASSWORD): str})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Backup integration."""
    hass.data[DOMAIN] = backup_manager = BackupManager(hass)
    await backup_manager.async_setup()

    with_hassio = is_hassio(hass)

    async_register_websocket_handlers(hass, with_hassio)

    if with_hassio:
        if DOMAIN in config:
            LOGGER.error(
                "The backup integration is not supported on this installation method, "
                "please remove it from your configuration"
            )
        return True

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
