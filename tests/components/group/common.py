"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.group import DOMAIN, GroupService, GroupServiceArgument
from homeassistant.core import HomeAssistant, callback


def reload(hass: HomeAssistant) -> None:
    """Reload the automation from config."""
    hass.add_job(async_reload, hass)


@callback
def async_reload(hass: HomeAssistant) -> None:
    """Reload the automation from config."""
    hass.async_create_task(hass.services.async_call(DOMAIN, GroupService.RELOAD))


def set_group(
    hass: HomeAssistant,
    object_id: str,
    name: str | None = None,
    entity_ids: list[str] | None = None,
    icon: str | None = None,
    add: list[str] | None = None,
) -> None:
    """Create/Update a group."""
    hass.add_job(
        async_set_group,
        hass,
        object_id,
        name,
        entity_ids,
        icon,
        add,
    )


@callback
def async_set_group(
    hass: HomeAssistant,
    object_id: str,
    name: str | None = None,
    entity_ids: list[str] | None = None,
    icon: str | None = None,
    add: list[str] | None = None,
) -> None:
    """Create/Update a group."""
    data = {
        key: value
        for key, value in (
            (GroupServiceArgument.OBJECT_ID, object_id),
            (GroupServiceArgument.NAME, name),
            (GroupServiceArgument.ENTITIES, entity_ids),
            (GroupServiceArgument.ICON, icon),
            (GroupServiceArgument.ADD_ENTITIES, add),
        )
        if value is not None
    }

    hass.async_create_task(hass.services.async_call(DOMAIN, GroupService.SET, data))


@callback
def async_remove(hass: HomeAssistant, object_id: str) -> None:
    """Remove a user group."""
    data = {GroupServiceArgument.OBJECT_ID: object_id}
    hass.async_create_task(hass.services.async_call(DOMAIN, GroupService.REMOVE, data))
