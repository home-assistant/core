"""Provide configuration end points for Customize."""
import asyncio

from homeassistant.components.config import EditKeyBasedConfigView
from homeassistant.components import SERVICE_RELOAD_CORE_CONFIG
from homeassistant.config import DATA_CUSTOMIZE

import homeassistant.helpers.config_validation as cv
from homeassistant.core import DOMAIN as CORE_DOMAIN

CONFIG_PATH = 'customize.yaml'


@asyncio.coroutine
def async_setup(hass):
    """Set up the Customize config API."""
    @asyncio.coroutine
    def hook(hass):
        """Hook to call after updating cutomization file."""
        yield from hass.services.async_call(
            CORE_DOMAIN, SERVICE_RELOAD_CORE_CONFIG)

    class CustomizeConfigView(EditKeyBasedConfigView):
        """Configure a list of entries."""

        def _get_value(self, data, config_key):
            """Get value."""
            customize = hass.data.get(DATA_CUSTOMIZE, {}).get(config_key)
            return {'global': customize, 'local': data.get(config_key, {})}

        def _write_value(self, data, config_key, new_value):
            """Set value."""
            data[config_key] = new_value

            state = hass.states.get(config_key)
            state_attributes = dict(state.attributes)
            state_attributes.update(new_value)
            hass.states.async_set(config_key, state.state, state_attributes)

    hass.http.register_view(CustomizeConfigView(
        'customize', 'config', CONFIG_PATH, cv.entity_id, dict,
        post_write_hook=hook
    ))

    return True
