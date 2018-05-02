"""Provide configuration end points for Automations."""
import asyncio
from collections import OrderedDict
import uuid

from homeassistant.const import CONF_ID
from homeassistant.components.config import EditIdBasedConfigView
from homeassistant.components.automation import (
    PLATFORM_SCHEMA, DOMAIN, async_reload)
import homeassistant.helpers.config_validation as cv


CONFIG_PATH = 'automations.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Automation config API."""
    hass.http.register_view(EditAutomationConfigView(
        DOMAIN, 'config', CONFIG_PATH, cv.string,
        PLATFORM_SCHEMA, post_write_hook=async_reload
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
