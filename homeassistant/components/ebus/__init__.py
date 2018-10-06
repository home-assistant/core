"""
Provides functionality to interact with ebus devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ebus/
"""
from datetime import timedelta
import logging

from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'ebus'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(seconds=10)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up climate devices."""
    component = hass.data[DOMAIN] = \
        EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)
