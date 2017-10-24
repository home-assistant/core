"""Provide configuration end points for Groups."""
import asyncio

from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components.group import GROUP_SCHEMA
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'groups.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Group config API."""
    hass.http.register_view(EditKeyBasedConfigView(
        'group', 'config', CONFIG_PATH, cv.slug, GROUP_SCHEMA
    ))
    return True
