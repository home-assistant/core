"""Provide configuration end points for Customize."""
import asyncio

from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components import async_reload_core_config
from homeassistant.config import DATA_CUSTOMIZE

import homeassistant.helpers.config_validation as cv

CONFIG_PATH = 'customize.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Customize config API."""
    hass.http.register_view(CustomizeConfigView(
        'customize', 'config', CONFIG_PATH, cv.entity_id, dict,
        post_write_hook=async_reload_core_config
    ))

    return True


class CustomizeConfigView(EditKeyBasedConfigView):
    """Configure a list of entries."""

    def _get_value(self, hass, data, config_key):
        """Get value."""
        customize = hass.data.get(DATA_CUSTOMIZE, {}).get(config_key) or {}
        return {'global': customize, 'local': data.get(config_key, {})}

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        data[config_key] = new_value

        state = hass.states.get(config_key)
        state_attributes = dict(state.attributes)
        state_attributes.update(new_value)
        hass.states.async_set(config_key, state.state, state_attributes)
