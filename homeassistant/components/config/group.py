"""Provide configuration end points for Groups."""
import asyncio
from homeassistant.const import SERVICE_RELOAD
from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components.group import DOMAIN, GROUP_SCHEMA
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'groups.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Group config API."""
    @asyncio.coroutine
    def hook(hass):
        """post_write_hook for Config View that reloads groups."""
        yield from hass.services.async_call(DOMAIN, SERVICE_RELOAD)

    hass.http.register_view(EditKeyBasedConfigView(
        'group', 'config', CONFIG_PATH, cv.slug, GROUP_SCHEMA,
        post_write_hook=hook
    ))
    return True
