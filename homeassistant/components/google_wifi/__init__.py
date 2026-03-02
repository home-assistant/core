"""The google_wifi component."""
"""Note that this also works for 'nest wifi' and 'onhub' routers/points"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

#Load the sensor.py file-- migrated from the legacy Google_Wifi integration
PLATFORMS = [Platform.SENSOR]


#Pull in the config flow - entry: ConfigEntry comes from the config flow.
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up My Custom Integration from a config entry."""
    # Register a listener for when the entry is updated (reconfigured)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    #Retrieve the IP address and name saved during the config flow
    ip_address = entry.data[CONF_IP_ADDRESS]
    name = entry.data.get(CONF_NAME, "Google Wifi")
    #Debug log
    _LOGGER.debug("Starting setup for device %s at IP: %s", name, ip_address)

    #Store the data to can access it later
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "ip_address": ip_address,
        "name": name,
    }

    #Tell Home Assistant to set up the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry when the user deletes or disables the integration."""
    
    # Tell Home Assistant to unload the platforms we set up earlier
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # If successful, remove the stored data from memory
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
