"""Provides triggers for timers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from . import ATTR_LAST_TRANSITION, DOMAIN

TRIGGERS: dict[str, type[Trigger]] = {
    "cancelled": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "cancelled"
    ),
    "finished": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "finished"
    ),
    "paused": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "paused"
    ),
    "restarted": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "restarted"
    ),
    "started": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_LAST_TRANSITION)}, "started"
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for timers."""
    return TRIGGERS
