"""The Backup integration."""

from homeassistant.core import HomeAssistant, ServiceCall
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
    BackupPlatformProtocol,
    BackupReaderWriter,
    CoreBackupReaderWriter,
    CreateBackupEvent,
    ManagerBackup,
    NewBackup,
    WrittenBackup,
)
from .models import AddonInfo, AgentBackup, Folder
from .websocket import async_register_websocket_handlers

__all__ = [
    "AddonInfo",
    "AgentBackup",
    "ManagerBackup",
    "BackupAgent",
    "BackupAgentError",
    "BackupAgentPlatformProtocol",
    "BackupPlatformProtocol",
    "BackupReaderWriter",
    "CreateBackupEvent",
    "Folder",
    "LocalBackupAgent",
    "NewBackup",
    "WrittenBackup",
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

    if not with_hassio:
        hass.services.async_register(DOMAIN, "create", async_handle_create_service)

    async_register_http_views(hass)

    return True
