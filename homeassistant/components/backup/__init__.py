"""The Backup integration."""
from homeassistant.components.hassio import is_hassio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER
from .http import async_register_http_views
from .manager import BackupManager
from .websocket import async_register_websocket_handlers


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Backup integration."""
    if is_hassio(hass):
        LOGGER.warning(
            "The backup integration is not supported on this installation method, "
            "please remove it from your configuration"
        )
        return False

    hass.data[DOMAIN] = manager = BackupManager(hass)

    if not manager.backup_dir.exists():
        LOGGER.debug("Creating backup directory")
        hass.async_add_executor_job(manager.backup_dir.mkdir)

    async_register_websocket_handlers(hass)
    async_register_http_views(hass)

    return True
