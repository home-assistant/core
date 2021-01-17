"""Support for AIS SUPLA MQTT"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the AI Speaker integration."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up AI Speaker from a config entry."""
    # web_session = aiohttp_client.async_get_clientsession(hass)
    # ais = AisWebService(hass.loop, web_session, entry.data["host"])
    # hass.data[DOMAIN][entry.entry_id] = ais

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return True
