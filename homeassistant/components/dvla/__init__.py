"""The DVLA integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REG_NUMBER, DOMAIN
from .coordinator import DVLACoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the DVLA Vehicle Enquiry Service component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a config entry."""

    session = async_get_clientsession(hass)

    coordinator = DVLACoordinator(
        hass,
        entry,
        session,
        entry.data[CONF_REG_NUMBER],
    )
    await coordinator.async_config_entry_first_refresh()

    hass_data = dict(entry.data)
    hass_data["coordinator"] = coordinator
    entry.runtime_data = hass_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
