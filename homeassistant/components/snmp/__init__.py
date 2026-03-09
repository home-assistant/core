"""The snmp component.

This file handles the high-level setup of the 'snmp' integration.
When a Config Entry is created or loaded, this is the first place Home Assistant looks.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .util import async_get_snmp_engine

# PLATFORMS lists the types of entities this integration supports.
# In this case, we are only supporting 'device_tracker' for now.
# Home Assistant will look for a 'device_tracker.py' file in this same directory.
PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

# __all__ defines what is exported when someone does 'from . import *'
__all__ = ["async_get_snmp_engine"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SNMP from a config entry.
    
    This function is called by Home Assistant whenever a Config Entry is loaded
    (e.g., during startup or when the user adds it via the UI).
    """
    # This line tells Home Assistant to go and look for the platforms listed in 
    # the PLATFORMS variable (device_tracker.py) and set them up.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Return True to indicate that setup was successful.
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.
    
    This function is called when a user deletes the integration or disables it.
    It ensures that all associated entities are removed and resources cleaned up.
    """
    # This line shuts down the platforms we started in 'async_setup_entry'.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
