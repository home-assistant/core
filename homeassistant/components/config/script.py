"""Provide configuration end points for scripts."""
import asyncio

from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components.script import (
    DOMAIN, SCRIPT_ENTRY_SCHEMA)
from homeassistant.const import SERVICE_RELOAD
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass


CONFIG_PATH = 'scripts.yaml'


@bind_hass
def async_reload(hass):
    """Reload the scripts from config.

    Returns a coroutine object.
    """
    return hass.services.async_call(DOMAIN, SERVICE_RELOAD)


@asyncio.coroutine
def async_setup(hass):
    """Set up the script config API."""
    hass.http.register_view(EditKeyBasedConfigView(
        'script', 'config', CONFIG_PATH, cv.slug, SCRIPT_ENTRY_SCHEMA,
        post_write_hook=async_reload
    ))
    return True
