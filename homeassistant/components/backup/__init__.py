"""The Backup integration."""

from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery_flow
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
from .config import BackupConfig, CreateBackupParametersDict
from .const import DATA_MANAGER, DOMAIN
from .coordinator import BackupConfigEntry, BackupDataUpdateCoordinator
from .http import async_register_http_views
from .manager import (
    AddonErrorData,
    BackupManager,
    BackupManagerError,
    BackupPlatformEvent,
    BackupPlatformProtocol,
    BackupReaderWriter,
    BackupReaderWriterError,
    CoreBackupReaderWriter,
    CreateBackupEvent,
    CreateBackupStage,
    CreateBackupState,
    IdleEvent,
    IncorrectPasswordError,
    ManagerBackup,
    NewBackup,
    RestoreBackupEvent,
    RestoreBackupStage,
    RestoreBackupState,
    WrittenBackup,
)
from .models import AddonInfo, AgentBackup, BackupNotFound, Folder
from .services import async_setup_services
from .util import suggested_filename, suggested_filename_from_name_date
from .websocket import async_register_websocket_handlers

__all__ = [
    "AddonErrorData",
    "AddonInfo",
    "AgentBackup",
    "BackupAgent",
    "BackupAgentError",
    "BackupAgentPlatformProtocol",
    "BackupConfig",
    "BackupManagerError",
    "BackupNotFound",
    "BackupPlatformEvent",
    "BackupPlatformProtocol",
    "BackupReaderWriter",
    "BackupReaderWriterError",
    "CreateBackupEvent",
    "CreateBackupParametersDict",
    "CreateBackupStage",
    "CreateBackupState",
    "Folder",
    "IdleEvent",
    "IncorrectPasswordError",
    "LocalBackupAgent",
    "ManagerBackup",
    "NewBackup",
    "RestoreBackupEvent",
    "RestoreBackupStage",
    "RestoreBackupState",
    "WrittenBackup",
    "async_get_manager",
    "suggested_filename",
    "suggested_filename_from_name_date",
]

PLATFORMS = [Platform.EVENT, Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Backup integration."""
    with_hassio = is_hassio(hass)

    reader_writer: BackupReaderWriter
    if not with_hassio:
        reader_writer = CoreBackupReaderWriter(hass)
    else:
        # pylint: disable-next=hass-component-root-import
        from homeassistant.components.hassio.backup import (  # noqa: PLC0415
            SupervisorBackupReaderWriter,
        )

        reader_writer = SupervisorBackupReaderWriter(hass)

    backup_manager = BackupManager(hass, reader_writer)
    hass.data[DATA_MANAGER] = backup_manager
    await backup_manager.async_setup()

    async_register_websocket_handlers(hass, with_hassio)

    async_setup_services(hass)

    async_register_http_views(hass)

    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: BackupConfigEntry) -> bool:
    """Set up a config entry."""
    backup_manager: BackupManager = hass.data[DATA_MANAGER]
    coordinator = BackupDataUpdateCoordinator(hass, entry, backup_manager)
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(coordinator.async_unsubscribe)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BackupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def async_get_manager(hass: HomeAssistant) -> BackupManager:
    """Get the backup manager instance.

    Raises HomeAssistantError if the backup integration is not available.
    """
    if DATA_MANAGER not in hass.data:
        raise HomeAssistantError("Backup integration is not available")

    return hass.data[DATA_MANAGER]
