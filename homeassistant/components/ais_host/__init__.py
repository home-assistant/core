"""Support for the definition of AIS hostname."""
import logging

from .config_flow import configured_host
from .const import DOMAIN
from homeassistant import config_entries

_LOGGER = logging.getLogger(__name__)


ICON_HOME = 'mdi:home'
ICON_IMPORT = 'mdi:import'

async def async_setup(hass, config):
    """Set up configured zones as well as home assistant zone if necessary."""
    hass.data[DOMAIN] = {}
    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_USER},
        data={}
    ))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up zone as config entry."""
    entry = config_entry.data

    hass.async_create_task()
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    return True
