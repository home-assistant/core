"""The google_wifi component."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# Define the schema for YAML validation
# This is for migration from the legacy YAML configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_IP_ADDRESS): cv.string,
                        vol.Optional(CONF_NAME, default="Google Wifi"): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Load the sensor.py file-- migrated from the legacy Google_Wifi integration
PLATFORMS = [Platform.SENSOR]


# Pull in the config flow - entry: ConfigEntry comes from the config flow.
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Wifi from a config entry."""

    # Store the entry data directly in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    # Handle renames
    entry.async_on_unload(entry.add_update_listener(update_listener))

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Google Wifi component from YAML."""
    if DOMAIN not in config:
        return True

    for entry_config in config[DOMAIN]:
        # We start a background task to initiate the import flow
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=entry_config,
            )
        )

    return True
