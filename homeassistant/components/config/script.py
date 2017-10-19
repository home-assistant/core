"""Provide configuration end points for scripts."""
import asyncio

from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components.script import SCRIPT_ENTRY_SCHEMA, async_reload
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'scripts.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the script config API."""
    hass.http.register_view(EditKeyBasedConfigView(
        'script', 'config', CONFIG_PATH, cv.slug, SCRIPT_ENTRY_SCHEMA,
        post_write_hook=async_reload
    ))
    return True
