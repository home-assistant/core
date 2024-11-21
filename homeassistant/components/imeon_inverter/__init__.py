"""Initialize the Imeon component."""

from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import InverterConfigEntry, InverterCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# __INIT__ #
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Load the integration into HASSOS (asynchronous).

    This function recovers config entries and for each one create
    the HUB instances needed to update data. It then updates config
    entries accordingly. Also creates services actions for each
    entry created (those are named dynamically).

    Services provided for each inverter :
        inverter_mode  : <str> (smg | bup | ong | ofg)
        mppt           : [<int>, <int>]
        feed_in        : <bool>
        injection_power: <int>
        lcd_time       : <int>
        night_discharge: <bool>
        grid_charge    : <bool>
        relay          : <bool>
        ac_output      : <bool>
        smartload      : read-only, no input
    """

    # Re-instanciate HUBs and services on startup
    entries = hass.config_entries.async_entries(DOMAIN)

    for entry in entries:
        # Create the corresponding HUB
        data = {
            "address": entry.data.get("address", ""),
            "username": entry.data.get("username", ""),
            "password": entry.data.get("password", ""),
        }
        IC = InverterCoordinator(hass, entry, data)

        entry.runtime_data = IC

    # Return boolean to indicate that initialization was successfully
    return True


async def async_setup_entry(hass: HomeAssistant, entry: InverterConfigEntry) -> bool:
    """Handle the creation of a new config entry for the integration (asynchronous).

    This function creates the HUB corresponding to the data in the entry.
    It then updates the config entry accordingly. It forces a first
    update to avoid having empty data before the first refresh.
    After filtering the user's input through Unicodedata and RegEx
    the function will create a dashboard for this specific entry.
    """

    # Create the corresponding HUB
    data = {
        "address": entry.data.get("address", ""),
        "username": entry.data.get("username", ""),
        "password": entry.data.get("password", ""),
    }  # NOTE UUID allows updates instead of creating new hubs
    IC = InverterCoordinator(hass, entry, data)

    entry.runtime_data = IC

    # Call for HUB creation then each entity as a List
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Handle entry unloading."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
