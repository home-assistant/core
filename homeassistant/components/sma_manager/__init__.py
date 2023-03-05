"""SMA Manager Initializer"""

#  Copyright (c) 2023.
#  All rights reserved to the creator of the following script/program/app, please do not
#  use or distribute without prior authorization from the creator.
#  Creator: Antonio Manuel Nunes Goncalves
#  Email: amng835@gmail.com
#  LinkedIn: https://www.linkedin.com/in/antonio-manuel-goncalves-983926142/
#  Github: https://github.com/DEADSEC-SECURITY

# Home Assistant Imports
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Local Imports
from .const import DOMAIN, CONF_NAME, CONF_HOST, CONF_PORT, CONF_REFRESH_INTERVAL
from .SMA import SMA


PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """
    Configures the Integration

    @param hass:
    @param config:
    @return:
    """

    # Save to SMA object to state machine
    data = config.data
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = SMA(
        data[CONF_NAME], data[CONF_HOST], data[CONF_PORT], data[CONF_REFRESH_INTERVAL]
    )

    # Configure platforms
    hass.config_entries.async_setup_platforms(config, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """
    Unload config

    This is called when an entry/configured device is to be removed. The class
    needs to unload itself, and remove callbacks. See the classes for further
    details

    @param hass:
    @param config:
    @return:
    """

    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)

    return unload_ok
