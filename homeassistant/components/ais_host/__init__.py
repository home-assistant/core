"""Support for the definition of AIS hostname."""
import logging

from .config_flow import configured_host
from .const import DOMAIN
from homeassistant import config_entries

_LOGGER = logging.getLogger(__name__)


ICON_HOME = 'mdi:home'
ICON_IMPORT = 'mdi:import'

async def async_setup(hass, config):
    """Set up if necessary."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up ais host as config entry."""
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    return True
