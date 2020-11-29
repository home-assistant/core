"""Support for Transports Metropolitans de Barcelona."""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from .const import CONF_APP_ID, CONF_APP_KEY, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_APP_ID): cv.string,
                vol.Required(CONF_APP_KEY): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up TMB sensors based on a config config."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = config[DOMAIN]

    return True


async def async_setup_entry(hass, entry):
    """Set up TMB sensors based on a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True
