"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.group import (
    ATTR_ADD_ENTITIES, ATTR_CONTROL, ATTR_ENTITIES, ATTR_OBJECT_ID, ATTR_VIEW,
    ATTR_VISIBLE, DOMAIN, SERVICE_REMOVE, SERVICE_SET, SERVICE_SET_VISIBILITY)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_ICON, ATTR_NAME, SERVICE_RELOAD)
from homeassistant.core import callback
from homeassistant.loader import bind_hass


@bind_hass
def reload(hass):
    """Reload the automation from config."""
    hass.add_job(async_reload, hass)


@callback
@bind_hass
def async_reload(hass):
    """Reload the automation from config."""
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_RELOAD))


@bind_hass
def set_group(hass, object_id, name=None, entity_ids=None, visible=None,
              icon=None, view=None, control=None, add=None):
    """Create/Update a group."""
    hass.add_job(
        async_set_group, hass, object_id, name, entity_ids, visible, icon,
        view, control, add)


@callback
@bind_hass
def async_set_group(hass, object_id, name=None, entity_ids=None, visible=None,
                    icon=None, view=None, control=None, add=None):
    """Create/Update a group."""
    data = {
        key: value for key, value in [
            (ATTR_OBJECT_ID, object_id),
            (ATTR_NAME, name),
            (ATTR_ENTITIES, entity_ids),
            (ATTR_VISIBLE, visible),
            (ATTR_ICON, icon),
            (ATTR_VIEW, view),
            (ATTR_CONTROL, control),
            (ATTR_ADD_ENTITIES, add),
        ] if value is not None
    }

    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_SET, data))


@callback
@bind_hass
def async_remove(hass, object_id):
    """Remove a user group."""
    data = {ATTR_OBJECT_ID: object_id}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_REMOVE, data))


@bind_hass
def set_visibility(hass, entity_id=None, visible=True):
    """Hide or shows a group."""
    data = {ATTR_ENTITY_ID: entity_id, ATTR_VISIBLE: visible}
    hass.services.call(DOMAIN, SERVICE_SET_VISIBILITY, data)
