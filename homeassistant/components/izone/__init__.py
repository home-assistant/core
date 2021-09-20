"""Platform for the iZone AC."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_CONFIG, IZONE
from .discovery import async_start_discovery_service, async_stop_discovery_service

PLATFORMS = ["climate"]

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


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Register the iZone component config."""
    conf = config.get(IZONE)
    if not conf:
        return True

    hass.data[DATA_CONFIG] = conf

    # Explicitly added in the config file, create a config entry.
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_IMPORT}
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up from a config entry."""
    await async_start_discovery_service(hass)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload the config entry and stop discovery process."""
    await async_stop_discovery_service(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
