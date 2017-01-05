"""
Component to interface with various sensors that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/
"""
import asyncio
from datetime import timedelta
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa

DOMAIN = 'sensor'
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + '.{}'


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    yield from component.async_setup(config)
    return True
