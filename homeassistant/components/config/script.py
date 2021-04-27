"""Provide configuration end points for scripts."""
from homeassistant.components.script import DOMAIN, SCRIPT_ENTRY_SCHEMA
from homeassistant.components.script.config import async_validate_config_item
from homeassistant.config import SCRIPT_CONFIG_PATH
from homeassistant.const import SERVICE_RELOAD
import homeassistant.helpers.config_validation as cv

from . import EditKeyBasedConfigView


async def async_setup(hass):
    """Set up the script config API."""

    async def hook(action, config_key):
        """post_write_hook for Config View that reloads scripts."""
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)

    hass.http.register_view(
        EditScriptConfigView(
            DOMAIN,
            "config",
            SCRIPT_CONFIG_PATH,
            cv.slug,
            SCRIPT_ENTRY_SCHEMA,
            post_write_hook=hook,
            data_validator=async_validate_config_item,
        )
    )
    return True


class EditScriptConfigView(EditKeyBasedConfigView):
    """Edit script config."""

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        data[config_key] = new_value
