"""Provide configuration end points for scripts."""
from homeassistant.components.script import DOMAIN
from homeassistant.components.script.config import (
    SCRIPT_ENTITY_SCHEMA,
    async_validate_config_item,
)
from homeassistant.config import SCRIPT_CONFIG_PATH
from homeassistant.const import SERVICE_RELOAD
from homeassistant.helpers import config_validation as cv, entity_registry as er

from . import ACTION_DELETE, EditKeyBasedConfigView


async def async_setup(hass):
    """Set up the script config API."""

    async def hook(action, config_key):
        """post_write_hook for Config View that reloads scripts."""
        if action != ACTION_DELETE:
            await hass.services.async_call(DOMAIN, SERVICE_RELOAD)
            return

        ent_reg = er.async_get(hass)

        entity_id = ent_reg.async_get_entity_id(DOMAIN, DOMAIN, config_key)

        if entity_id is None:
            return

        ent_reg.async_remove(entity_id)

    hass.http.register_view(
        EditScriptConfigView(
            DOMAIN,
            "config",
            SCRIPT_CONFIG_PATH,
            cv.slug,
            SCRIPT_ENTITY_SCHEMA,
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
