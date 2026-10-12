"""The Schlage integration."""

from pycognito.exceptions import WarrantException
import pyschlage

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SchlageConfigEntry, SchlageDataUpdateCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Schlage component."""
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SchlageConfigEntry) -> bool:
    """Set up Schlage from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    try:
        auth = await hass.async_add_executor_job(pyschlage.Auth, username, password)
    except WarrantException as ex:
        raise ConfigEntryAuthFailed from ex

    coordinator = SchlageDataUpdateCoordinator(
        hass, entry, username, pyschlage.Schlage(auth)
    )
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SchlageConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
