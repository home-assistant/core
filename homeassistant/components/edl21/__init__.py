"""The edl21 component."""

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import CONF_SERIAL_PORT, DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SERIAL_PORT): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up EDL21 integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, Platform.SENSOR)
    )

    return True
