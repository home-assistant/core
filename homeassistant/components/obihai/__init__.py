"""The Obihai integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .connectivity import ObihaiConnection
from .const import LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    version = entry.version

    LOGGER.debug("Migrating from version %s", version)
    if version != 2:
        requester = ObihaiConnection(
            entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
        await hass.async_add_executor_job(requester.update)

        new_unique_id = await hass.async_add_executor_job(
            requester.pyobihai.get_device_mac
        )
        hass.config_entries.async_update_entry(entry, unique_id=new_unique_id)

        entry.version = 2

    LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
