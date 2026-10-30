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
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN, NODE_STATUSES
from ..helpers import (
    async_bypass_dynamic_config_validation,
    async_get_node_from_device_id,
)

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
    """Validate the group behaviors get a to status to count.

    The first and all behaviors count the nodes whose status satisfies the
    trigger. Without to, any status outside from would count, and sleeping
    nodes are never alive, so a mixed network would miscount.
    """
    if options[ATTR_BEHAVIOR] != BEHAVIOR_EACH and not options.get(CONF_TO):
        raise probatio.Invalid(
            f"{ATTR_BEHAVIOR} {options[ATTR_BEHAVIOR]} requires {CONF_TO}"
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
    # A hidden node status sensor must still be watched.
    _include_hidden_entities = True
    _schema = _TRIGGER_SCHEMA

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        config = await super().async_validate_config(hass, config)
        device_ids = config[CONF_OPTIONS][ATTR_DEVICE_ID]
        if async_bypass_dynamic_config_validation(hass, {ATTR_DEVICE_ID: device_ids}):
            return config

        found_node = False
        for device_id in device_ids:
            try:
                node = async_get_node_from_device_id(hass, device_id)
            except ValueError:
                continue
            # The controller has no node status sensor to watch.
            if node.is_controller_node:
                raise probatio.Invalid(
                    f"Device {device_id} is the controller, which has no node status"
                )
            found_node = True
        if not found_node:
            raise probatio.Invalid("No nodes found for the given devices")
        return config

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
        self._is_group = self._options[ATTR_BEHAVIOR] != BEHAVIOR_EACH

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Keep only Z-Wave JS node status sensors."""
        ent_reg = er.async_get(self._hass)
        return {
            entity_id
            for entity_id in super().entity_filter(entities)
            if (entry := ent_reg.async_get(entity_id))
            and entry.platform == DOMAIN
            and entry.unique_id.endswith(".node_status")
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
        return (
            from_state.state != to_state.state
            # The first and all behaviors count matching states, not changes, so
            # a node already satisfying the trigger must not satisfy it again.
            and not (self._is_group and from_state.state in self._to_states)
            and (not self._from_states or from_state.state in self._from_states)
        )
