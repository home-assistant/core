"""Provide configuration end points for Z-Wave."""
import asyncio

from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components.zwave import DEVICE_CONFIG_SCHEMA_ENTRY
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'zwave_device_config.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Z-Wave config API."""
    hass.http.register_view(EditKeyBasedConfigView(
        'zwave', 'device_config', CONFIG_PATH, cv.entity_id,
        DEVICE_CONFIG_SCHEMA_ENTRY
    ))
    return True
