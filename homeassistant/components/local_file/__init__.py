"""The local_file component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services
from .util import check_file_path_access

PLATFORMS = [Platform.CAMERA]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Local file integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Local file from a config entry."""
    file_path: str = entry.options[CONF_FILE_PATH]
    if not await hass.async_add_executor_job(check_file_path_access, file_path):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="not_readable_path",
            translation_placeholders={"file_path": file_path},
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Local file config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
