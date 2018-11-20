"""Provide configuration end points for Groups."""
from homeassistant.const import SERVICE_RELOAD
from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components.group import DOMAIN, GROUP_SCHEMA
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'groups.yaml'


async def async_setup(hass):
    """Set up the Group config API."""
    async def hook(hass):
        """post_write_hook for Config View that reloads groups."""
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)

    hass.http.register_view(EditKeyBasedConfigView(
        'group', 'config', CONFIG_PATH, cv.slug, GROUP_SCHEMA,
        post_write_hook=hook
    ))
    return True
