"""Provide configuration end points for Automations."""
from collections import OrderedDict
import uuid

from homeassistant.components.automation import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import CONF_ID, SERVICE_RELOAD
import homeassistant.helpers.config_validation as cv

from . import EditIdBasedConfigView

CONFIG_PATH = 'automations.yaml'


async def async_setup(hass):
    """Set up the Automation config API."""
    async def hook(hass):
        """post_write_hook for Config View that reloads automations."""
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)

    hass.http.register_view(EditAutomationConfigView(
        DOMAIN, 'config', CONFIG_PATH, cv.string,
        PLATFORM_SCHEMA, post_write_hook=hook
    ))
    return True


class EditAutomationConfigView(EditIdBasedConfigView):
    """Edit automation config."""

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        index = None
        for index, cur_value in enumerate(data):
            # When people copy paste their automations to the config file,
            # they sometimes forget to add IDs. Fix it here.
            if CONF_ID not in cur_value:
                cur_value[CONF_ID] = uuid.uuid4().hex

            elif cur_value[CONF_ID] == config_key:
                break
        else:
            cur_value = OrderedDict()
            cur_value[CONF_ID] = config_key
            index = len(data)
            data.append(cur_value)

        # Iterate through some keys that we want to have ordered in the output
        updated_value = OrderedDict()
        for key in ('id', 'alias', 'trigger', 'condition', 'action'):
            if key in cur_value:
                updated_value[key] = cur_value[key]
            if key in new_value:
                updated_value[key] = new_value[key]

        # We cover all current fields above, but just in case we start
        # supporting more fields in the future.
        updated_value.update(cur_value)
        updated_value.update(new_value)
        data[index] = updated_value
