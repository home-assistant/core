"""Platform for the iZone AC."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_CONFIG, IZONE
from .discovery import async_start_discovery_service, async_stop_discovery_service

PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = vol.Schema(
    {
        IZONE: vol.Schema(
            {
                vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the iZone component config."""

    # Check for manually added config, this may exclude some devices
    if conf := config.get(IZONE):
        hass.data[DATA_CONFIG] = conf

        # Explicitly added in the config file, create a config entry.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                IZONE, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    # Start the discovery service
    await async_start_discovery_service(hass)

    async def shutdown_event(event):
        await async_stop_discovery_service(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_event)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and stop discovery process."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
