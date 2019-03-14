"""Binary sensor platform for mobile_app."""
from .const import ATTR_SENSOR_TYPE_BINARY_SENSOR as ENTITY_TYPE

from .entity import async_setup_mobile_app_entry

DEPENDENCIES = ['mobile_app']


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app binary sensor from a config entry."""
    return await async_setup_mobile_app_entry(ENTITY_TYPE, hass, config_entry,
                                              async_add_entities)
