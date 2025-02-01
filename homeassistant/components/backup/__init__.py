"""The Backup integration."""

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.typing import ConfigType

# Pre-import backup to avoid it being imported
# later when the import executor is busy and delaying
# startup
from . import backup  # noqa: F401
from .agent import (
    BackupAgent,
    BackupAgentError,
    BackupAgentPlatformProtocol,
    LocalBackupAgent,
)
from .const import DATA_MANAGER, DOMAIN
from .http import async_register_http_views
from .manager import (
    BackupManager,
    BackupManagerError,
    BackupPlatformProtocol,
    BackupReaderWriter,
    BackupReaderWriterError,
    CoreBackupReaderWriter,
    CreateBackupEvent,
    IdleEvent,
    IncorrectPasswordError,
    ManagerBackup,
    NewBackup,
    RestoreBackupEvent,
    RestoreBackupState,
    WrittenBackup,
)
from .models import AddonInfo, AgentBackup, Folder
from .util import suggested_filename, suggested_filename_from_name_date
from .websocket import async_register_websocket_handlers

__all__ = [
    "AddonInfo",
    "AgentBackup",
    "BackupAgent",
    "BackupAgentError",
    "BackupAgentPlatformProtocol",
    "BackupManagerError",
    "BackupPlatformProtocol",
    "BackupReaderWriter",
    "BackupReaderWriterError",
    "CreateBackupEvent",
    "Folder",
    "IdleEvent",
    "IncorrectPasswordError",
    "LocalBackupAgent",
    "ManagerBackup",
    "NewBackup",
    "RestoreBackupEvent",
    "RestoreBackupState",
    "WrittenBackup",
    "async_get_manager",
    "suggested_filename",
    "suggested_filename_from_name_date",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


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
            agent_ids=[agent_id],
            include_addons=None,
            include_all_addons=False,
            include_database=True,
            include_folders=None,
            include_homeassistant=True,
            name=None,
            password=None,
        )

    async def async_handle_create_automatic_service(call: ServiceCall) -> None:
        """Service handler for creating automatic backups."""
        await backup_manager.async_create_automatic_backup()

    if not with_hassio:
        hass.services.async_register(DOMAIN, "create", async_handle_create_service)
    hass.services.async_register(
        DOMAIN, "create_automatic", async_handle_create_automatic_service
    )

    async_register_http_views(hass)

    return True


@callback
def async_get_manager(hass: HomeAssistant) -> BackupManager:
    """Get the backup manager instance.

    Raises HomeAssistantError if the backup integration is not available.
    """
    if DATA_MANAGER not in hass.data:
        raise HomeAssistantError("Backup integration is not available")

    return hass.data[DATA_MANAGER]
