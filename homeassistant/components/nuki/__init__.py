"""The nuki component."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PORT, DOMAIN

PLATFORMS = ["lock"]
UPDATE_INTERVAL = timedelta(seconds=30)

NUKI_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Required(CONF_TOKEN): cv.string,
        },
    )
)


async def async_setup(hass, config):
    """Set up the Nuki component."""
    hass.data.setdefault(DOMAIN, {})

    for platform in PLATFORMS:
        confs = config.get(platform)
        if confs is None:
            continue

        for conf in confs:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the Nuki entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, LOCK_DOMAIN)
    )

    return True
