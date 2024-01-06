"""The Backup integration."""
from homeassistant.components.hassio import is_hassio
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER
from .http import async_register_http_views
from .manager import BackupManager
from .websocket import async_register_websocket_handlers

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Backup integration."""
    if is_hassio(hass):
        LOGGER.error(
            "The backup integration is not supported on this installation method, "
            "please remove it from your configuration"
        )
        return False

    backup_manager = BackupManager(hass)
    hass.data[DOMAIN] = backup_manager

    async def async_handle_create_service(call: ServiceCall) -> None:
        """Service handler for creating backups."""
        await backup_manager.generate_backup()

    hass.services.async_register(DOMAIN, "create", async_handle_create_service)

    async_register_websocket_handlers(hass)
    async_register_http_views(hass)

    return True
