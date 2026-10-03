"""Offer Z-Wave JS node status automation trigger."""

from dataclasses import replace
from typing import Any, override

import probatio

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_DEVICE_ID, CONF_FOR, CONF_OPTIONS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_EACH,
    BEHAVIOR_FIRST,
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

_STATUS_LIST = probatio.All(probatio.EnsureList(), [probatio.In(NODE_STATUSES)])

_OPTIONS_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    probatio.Required(ATTR_DEVICE_ID): probatio.All(probatio.EnsureList(), [cv.string]),
    probatio.Required(ATTR_BEHAVIOR, default=BEHAVIOR_EACH): probatio.In(
        [BEHAVIOR_FIRST, BEHAVIOR_ALL, BEHAVIOR_EACH]
    ),
    probatio.Optional(CONF_FOR): cv.positive_time_period,
    probatio.Optional(CONF_FROM): _STATUS_LIST,
    probatio.Optional(CONF_TO): _STATUS_LIST,
}


def _validate_status_filter(options: dict[str, Any]) -> dict[str, Any]:
    """Validate the group behaviors get a status filter to count.

    The first and all behaviors count the nodes whose status satisfies the
    trigger, so without a filter every node counts and the group is vacuous.
    """
    if options[ATTR_BEHAVIOR] != BEHAVIOR_EACH and not (
        options.get(CONF_FROM) or options.get(CONF_TO)
    ):
        raise probatio.Invalid(
            f"{ATTR_BEHAVIOR} {options[ATTR_BEHAVIOR]} requires "
            f"{CONF_FROM} or {CONF_TO}"
        )
    return options


_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS, default={}): probatio.All(
            _OPTIONS_SCHEMA_DICT, _validate_status_filter
        )
    }
)


class NodeStatusTrigger(EntityTriggerBase):
    """Trigger on Z-Wave JS node status changes."""

    _domain_specs = {SENSOR_DOMAIN: DomainSpec()}
    _primary_entities_only = False
    _schema = _TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        options = config.options or {}
        # A node is picked as a device; the base class tracks the node status
        # sensor each one expands to.
        super().__init__(
            hass, replace(config, target={ATTR_DEVICE_ID: options[ATTR_DEVICE_ID]})
        )
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
        """Check the status changed from a wanted, not already matching, status."""
        return (
            from_state.state != to_state.state
            # A status already satisfying the trigger must not satisfy it again:
            # the first and all behaviors count matching states, not changes.
            and from_state.state not in self._to_states
            and (not self._from_states or from_state.state in self._from_states)
        )
