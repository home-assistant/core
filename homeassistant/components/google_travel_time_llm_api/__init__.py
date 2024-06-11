"""The Google Travel Time LLM API integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import DOMAIN
from .llm_api import GoogleMapsTravelTimeAPI


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Travel Time LLM API from a config entry."""
    api_key = entry.data.get("api_key")
    if not api_key:
        return False

    api_instance = GoogleMapsTravelTimeAPI(hass, api_key)
    await async_setup_api(hass, api_instance)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = api_instance
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_setup_api(
    hass: HomeAssistant, api_instance: GoogleMapsTravelTimeAPI
) -> None:
    """Register the API with Home Assistant."""
    llm.async_register_api(hass, api_instance)
