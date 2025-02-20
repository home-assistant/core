import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_ACCESS_TOKEN
from .const import DOMAIN
from redgtech_api import RedgtechAPI
from .coordinator import RedgtechDataUpdateCoordinator
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

@dataclass
class RedgtechEntryData:
    config: dict
    coordinator: RedgtechDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Redgtech from a config entry."""
    _LOGGER.debug("Setting up Redgtech entry: %s", entry.entry_id)

    access_token = entry.data[CONF_ACCESS_TOKEN]
    api = RedgtechAPI(access_token)
    coordinator = RedgtechDataUpdateCoordinator(hass, api)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.error("Error fetching data from API: %s", e)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = RedgtechEntryData(
        config=entry.data,
        coordinator=coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Successfully set up Redgtech entry: %s", entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Redgtech entry: %s", entry.entry_id)
    api = RedgtechAPI(entry.data[CONF_ACCESS_TOKEN])
    await api.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)