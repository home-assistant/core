"""Built-in Home Assistant conversation agent."""

from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.typing import ConfigType

from .const import CONVERSATION_DOMAIN, DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up assist conversation."""
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up assist conversation config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, [CONVERSATION_DOMAIN])
    return True
