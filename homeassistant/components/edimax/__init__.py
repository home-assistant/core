"""The edimax component."""

from pyedimax.smartplug import SmartPlug
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    HomeAssistant,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_NAME
from .smartplug_adapter import SmartPlugAdapter

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

type EdimaxConfigEntry = ConfigEntry[SmartPlug]

EDIMAX_PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: EdimaxConfigEntry) -> bool:
    """Set up Edimax SmartPlug from a config entry."""

    host = str(entry.data.get(CONF_HOST))

    ediplugadapter = SmartPlugAdapter(hass, host)
    await ediplugadapter.async_update()
    entry.runtime_data = ediplugadapter

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EdimaxConfigEntry) -> bool:
    """Unload Edimax SmnartPlug config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
