"""Provide configuration end points for Customize."""
from homeassistant.components.homeassistant import SERVICE_RELOAD_CORE_CONFIG
from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.core import DOMAIN
import homeassistant.helpers.config_validation as cv

from . import EditKeyBasedConfigView

CONFIG_PATH = 'customize.yaml'


async def async_setup(hass):
    """Set up the Customize config API."""
    async def hook(hass):
        """post_write_hook for Config View that reloads groups."""
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD_CORE_CONFIG)

    hass.http.register_view(CustomizeConfigView(
        'customize', 'config', CONFIG_PATH, cv.entity_id, dict,
        post_write_hook=hook
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
