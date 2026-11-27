"""Shared helpers for the OpenWrt (ubus) integration."""

from homeassistant.components.automation import (
    automations_with_device,
    automations_with_entity,
)
from homeassistant.core import HomeAssistant, callback


@callback
def referencing_automations(
    hass: HomeAssistant,
    device_id: str | None,
    entity_id: str | None,
) -> list[str]:
    """Return the names of the automations referencing a device or entity."""
    ids = automations_with_device(hass, device_id) if device_id else []
    if entity_id:
        ids += automations_with_entity(hass, entity_id)
    names = []
    for automation_id in dict.fromkeys(ids):
        if (state := hass.states.get(automation_id)) is None:
            names.append(automation_id)
        else:
            names.append(state.name)
    return names
