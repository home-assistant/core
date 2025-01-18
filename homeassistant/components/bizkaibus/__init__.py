"""The Bizkaibus bus tracker component."""

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STOP_ID, DOMAIN
from .coordinator import BizkaibusUpdateCoordinator
from .sensor import BizkaibusSensor

PLATFORMS: list[Platform] = [Platform.SENSOR]
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend({vol.Required(CONF_STOP_ID): cv.string})
CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_STOP_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bizkaibus component."""
    # hass.states.async_set("hello_state.world", "Paulus")

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Config entry example."""
    # assuming API object stored here by __init__.py
    my_api = hass.data[DOMAIN][entry.entry_id]
    coordinator = BizkaibusUpdateCoordinator(hass, my_api)

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        BizkaibusSensor(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )
    return True
