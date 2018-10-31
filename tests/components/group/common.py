"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.group import ATTR_VISIBLE, DOMAIN, \
    SERVICE_SET_VISIBILITY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.loader import bind_hass


@bind_hass
def set_visibility(hass, entity_id=None, visible=True):
    """Hide or shows a group."""
    data = {ATTR_ENTITY_ID: entity_id, ATTR_VISIBLE: visible}
    hass.services.call(DOMAIN, SERVICE_SET_VISIBILITY, data)
