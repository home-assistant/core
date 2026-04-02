"""Provides triggers for device_trackers."""

import voluptuous as vol

from homeassistant.const import (
    CONF_OPTIONS,
    CONF_ZONE,
    STATE_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST,
    EntityTriggerBase,
    Trigger,
    TriggerConfig,
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
)

from .const import ATTR_IN_ZONES, DOMAIN

ZONE_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_ZONE): vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [cv.entity_domain("zone")],
            ),
        },
    }
)

_IN_ZONES_SPEC = {DOMAIN: DomainSpec(value_source=ATTR_IN_ZONES)}


class ZoneTriggerBase(EntityTriggerBase):
    """Base for zone-based device tracker triggers."""

    _domain_specs = _IN_ZONES_SPEC
    _schema = ZONE_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._zones: set[str] = set(self._options[CONF_ZONE])

    def _is_valid(self, state: State) -> bool:
        """Check if the state is valid (not unavailable/unknown)."""
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    def _in_target_zones(self, state: State) -> bool:
        """Check if the device is in any of the selected zones."""
        in_zones = set(self._get_tracked_value(state) or [])
        return bool(in_zones.intersection(self._zones))


class EnteredZoneTrigger(ZoneTriggerBase):
    """Trigger when a device tracker enters one of the selected zones."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the device was not already in any of the selected zones."""
        return self._is_valid(from_state) and not self._in_target_zones(from_state)

    def is_valid_state(self, state: State) -> bool:
        """Check that the device is now in at least one of the selected zones."""
        return self._is_valid(state) and self._in_target_zones(state)


class LeftZoneTrigger(ZoneTriggerBase):
    """Trigger when a device tracker leaves all of the selected zones."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the device was previously in at least one of the selected zones."""
        return self._is_valid(from_state) and self._in_target_zones(from_state)

    def is_valid_state(self, state: State) -> bool:
        """Check that the device is no longer in any of the selected zones."""
        return self._is_valid(state) and not self._in_target_zones(state)


TRIGGERS: dict[str, type[Trigger]] = {
    "entered_home": make_entity_target_state_trigger(DOMAIN, STATE_HOME),
    "entered_zone": EnteredZoneTrigger,
    "left_home": make_entity_origin_state_trigger(DOMAIN, from_state=STATE_HOME),
    "left_zone": LeftZoneTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for device trackers."""
    return TRIGGERS
