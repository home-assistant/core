"""The Barry App integration."""
import logging

from pybarry import Barry

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN

PLATFORMS = [
    "sensor",
]


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Barry component."""

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""

    barry_connection = Barry(
        access_token=entry.data[CONF_ACCESS_TOKEN],
    )
    hass.data[DOMAIN] = barry_connection

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True
