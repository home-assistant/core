"""The Backup integration."""

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.hassio import is_hassio

from .const import DATA_MANAGER, DOMAIN


async def _async_handle_create_service(call: ServiceCall) -> None:
    """Service handler for creating backups."""
    backup_manager = call.hass.data[DATA_MANAGER]
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


async def _async_handle_create_automatic_service(call: ServiceCall) -> None:
    """Service handler for creating automatic backups."""
    await call.hass.data[DATA_MANAGER].async_create_automatic_backup()


def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    if not is_hassio(hass):
        hass.services.async_register(DOMAIN, "create", _async_handle_create_service)
    hass.services.async_register(
        DOMAIN, "create_automatic", _async_handle_create_automatic_service
    )
