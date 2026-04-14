"""Provides conditions for device trackers."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.zone import ENTITY_ID_HOME as ENTITY_ID_HOME_ZONE
from homeassistant.const import CONF_OPTIONS, CONF_ZONE, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    ConditionConfig,
    EntityConditionBase,
    make_entity_state_condition,
)

from .const import ATTR_IN_ZONES, DOMAIN

ZONE_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
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


class ZoneConditionBase(EntityConditionBase):
    """Base for zone-based device tracker conditions."""

    _domain_specs = _IN_ZONES_SPEC
    _schema = ZONE_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._zones: set[str] = set(config.options[CONF_ZONE])

    def _in_target_zones(self, state: State) -> bool:
        """Check if the device is in any of the selected zones.

        For GPS-based trackers, uses the in_zones attribute.
        For scanner-based trackers (no in_zones attribute), infers from
        state: 'home' means the device is in zone.home.
        """
        if (in_zones := self._get_tracked_value(state)) is not None:
            return bool(set(in_zones).intersection(self._zones))
        # Scanner tracker: state 'home' means in zone.home
        if state.state == STATE_HOME:
            return ENTITY_ID_HOME_ZONE in self._zones
        return False


class InZoneCondition(ZoneConditionBase):
    """Condition that tests if a device tracker is in one of the selected zones."""

    def is_valid_state(self, entity_state: State) -> bool:
        """Check that the device is in at least one of the selected zones."""
        return self._in_target_zones(entity_state)


class NotInZoneCondition(ZoneConditionBase):
    """Condition that tests if a device tracker is not in any of the selected zones."""

    def is_valid_state(self, entity_state: State) -> bool:
        """Check that the device is not in any of the selected zones."""
        return not self._in_target_zones(entity_state)


CONDITIONS: dict[str, type[Condition]] = {
    "in_zone": InZoneCondition,
    "is_home": make_entity_state_condition(DOMAIN, STATE_HOME),
    "is_not_home": make_entity_state_condition(DOMAIN, STATE_NOT_HOME),
    "not_in_zone": NotInZoneCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for device trackers."""
    return CONDITIONS
