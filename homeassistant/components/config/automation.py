"""Provide configuration end points for Automations."""
import asyncio

from homeassistant.components.config import EditIdBasedConfigView
from homeassistant.components.automation import (
    PLATFORM_SCHEMA, DOMAIN, async_reload)
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'automations.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Automation config API."""
    hass.http.register_view(EditIdBasedConfigView(
        DOMAIN, 'config', CONFIG_PATH, cv.string,
        PLATFORM_SCHEMA, post_write_hook=async_reload
    ))
    return True
