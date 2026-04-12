"""Provides triggers for humidifiers."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

from .const import ATTR_ACTION, DOMAIN, HumidifierAction

TRIGGERS: dict[str, type[Trigger]] = {
    "started_drying": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_ACTION)}, HumidifierAction.DRYING
    ),
    "started_humidifying": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_ACTION)}, HumidifierAction.HUMIDIFYING
    ),
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_target_state_trigger(DOMAIN, STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for humidifiers."""
    return TRIGGERS
