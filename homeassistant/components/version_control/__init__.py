"""
Provide the functionality to add version_control entities.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/version_control/
"""
from datetime import timedelta
import logging

from homeassistant.helpers.entity_component import EntityComponent

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'version_control'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SCAN_INTERVAL = timedelta(minutes=5)

ATTR_BRANCH_NAME = 'branch_name'
ATTR_COMMIT_TITLE = 'commit_title'


async def async_setup(hass, config):
    """Track states and offer events for version control platforms."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Setup a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class VersionControlException(Exception):
    """Simple Exception class that can be explicitly caught."""

    pass
