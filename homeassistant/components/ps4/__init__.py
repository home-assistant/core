"""
Support for PlayStation 4 consoles.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ps4/
"""
import logging

from .config_flow import (  # noqa  pylint: disable=unused-import
    PlayStation4FlowHandler)
from .const import DOMAIN  # noqa: pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyps4-homeassistant==0.4.8']


async def async_setup(hass, config):
    """Set up the PS4 Component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up PS4 from a config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        config_entry, 'media_player'))
    return True


async def async_unload_entry(hass, entry):
    """Unload a PS4 config entry."""
    await hass.config_entries.async_forward_entry_unload(
        entry, 'media_player')
    return True
