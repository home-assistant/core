"""Offer Z-Wave JS node status automation trigger."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR,
    EntityTriggerBase,
    NotTriggeredReasonReporter,
    TriggerConfig,
)

from ..const import DOMAIN, NODE_STATUSES

# Relative platform type should be <SUBMODULE_NAME>
RELATIVE_PLATFORM_TYPE = f"{__name__.rsplit('.', maxsplit=1)[-1]}"

# Platform type should be <DOMAIN>.<SUBMODULE_NAME>
PLATFORM_TYPE = f"{DOMAIN}.{RELATIVE_PLATFORM_TYPE}"

CONF_FROM = "from"
CONF_TO = "to"

_STATUS_LIST = vol.All(cv.ensure_list, [vol.In(NODE_STATUSES)])

_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Optional(CONF_FROM): _STATUS_LIST,
    vol.Optional(CONF_TO): _STATUS_LIST,
}

_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR.extend(
    {vol.Required(CONF_OPTIONS, default={}): _OPTIONS_SCHEMA_DICT}
)


class NodeStatusTrigger(EntityTriggerBase):
    """Trigger on Z-Wave JS node status changes."""

    _domain_specs = {SENSOR_DOMAIN: DomainSpec()}
    _primary_entities_only = False
    _schema = _TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._from_states = set(self._options.get(CONF_FROM, []))
        self._to_states = set(self._options.get(CONF_TO, []))

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Keep only Z-Wave JS node status sensors."""
        ent_reg = er.async_get(self._hass)
        return {
            entity_id
            for entity_id in super().entity_filter(entities)
            if (entry := ent_reg.async_get(entity_id))
            and entry.platform == DOMAIN
            and entry.translation_key == "node_status"
        }

    @override
    def is_valid_state(
        self, state: State, report_not_triggered: NotTriggeredReasonReporter
    ) -> bool:
        """Check the new status can satisfy the trigger."""
        if self._to_states:
            return state.state in self._to_states
        return state.state not in self._from_states

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check the status changed from a wanted status."""
        return from_state.state != to_state.state and (
            not self._from_states or from_state.state in self._from_states
        )
