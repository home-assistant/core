"""The Sun WEG inverter sensor integration."""

from sunweg.api import APIHelper

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import CONF_PLANT_ID, DOMAIN, PLATFORMS
from .coordinator import SunWEGDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Load the saved entities."""
    api = APIHelper(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    if not await hass.async_add_executor_job(api.authenticate):
        raise ConfigEntryAuthFailed("Username or Password may be incorrect!")
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, entry.data[CONF_PLANT_ID], entry.data[CONF_NAME]
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
