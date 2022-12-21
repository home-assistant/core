"""Provide configuration end points for Scenes."""
import uuid

from homeassistant.components.scene import DOMAIN, PLATFORM_SCHEMA
from homeassistant.config import SCENE_CONFIG_PATH
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.helpers import config_validation as cv, entity_registry

from . import ACTION_DELETE, EditIdBasedConfigView


async def async_setup(hass):
    """Set up the Scene config API."""

    async def hook(action, config_key):
        """post_write_hook for Config View that reloads scenes."""
        if action != ACTION_DELETE:
            await hass.services.async_call(DOMAIN, SERVICE_RELOAD)
            return

        ent_reg = entity_registry.async_get(hass)

        entity_id = ent_reg.async_get_entity_id(DOMAIN, HA_DOMAIN, config_key)

        if entity_id is None:
            return

        ent_reg.async_remove(entity_id)

    hass.http.register_view(
        EditSceneConfigView(
            DOMAIN,
            "config",
            SCENE_CONFIG_PATH,
            cv.string,
            PLATFORM_SCHEMA,
            post_write_hook=hook,
        )
    )
    return True


class EditSceneConfigView(EditIdBasedConfigView):
    """Edit scene config."""

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        updated_value = {CONF_ID: config_key}
        # Iterate through some keys that we want to have ordered in the output
        for key in ("name", "entities"):
            if key in new_value:
                updated_value[key] = new_value[key]

        # We cover all current fields above, but just in case we start
        # supporting more fields in the future.
        updated_value.update(new_value)

        updated = False
        for index, cur_value in enumerate(data):
            # When people copy paste their scenes to the config file,
            # they sometimes forget to add IDs. Fix it here.
            if CONF_ID not in cur_value:
                cur_value[CONF_ID] = uuid.uuid4().hex

            elif cur_value[CONF_ID] == config_key:
                data[index] = updated_value
                updated = True

        if not updated:
            data.append(updated_value)
