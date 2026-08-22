"""Offer zone automation rules."""

import logging
from typing import TYPE_CHECKING, Any, cast, override

import voluptuous as vol

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    CONF_ZONE,
    EntityStateAttribute,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    location,
)
from homeassistant.helpers.automation import (
    DomainSpec,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR,
    EntityTriggerBase,
    NotTriggeredReasonReporter,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from . import condition
from .const import DOMAIN
from .helpers import get_in_zones_attribute

EVENT_ENTER = "enter"
EVENT_LEAVE = "leave"
DEFAULT_EVENT = EVENT_ENTER

_LOGGER = logging.getLogger(__name__)

_EVENT_DESCRIPTION = {EVENT_ENTER: "entering", EVENT_LEAVE: "leaving"}


def _state_has_zone_info(state: State) -> bool:
    """Return True if the state can be matched against a zone.

    For device_tracker and person entities an ``in_zones`` attribute is
    sufficient even when the state has no coordinates (e.g. a scanner-based
    tracker); other entities are matched by their coordinates.
    """
    return location.has_location(state) or (
        (in_zones_attr := get_in_zones_attribute(state)) is not None
        and in_zones_attr in state.attributes
    )


_LEGACY_OPTIONS_SCHEMA: dict[vol.Marker, Any] = {
    vol.Required(CONF_ENTITY_ID): cv.entity_ids_or_uuids,
    vol.Required(CONF_ZONE): cv.entity_id,
    vol.Required(CONF_EVENT, default=DEFAULT_EVENT): vol.Any(EVENT_ENTER, EVENT_LEAVE),
}

_LEGACY_TRIGGER_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): _LEGACY_OPTIONS_SCHEMA,
    },
)

# New-style zone trigger schema
_ZONE_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_ZONE): cv.entity_domain(DOMAIN),
        },
    }
)

_DOMAIN_SPECS: dict[str, DomainSpec] = {
    "person": DomainSpec(),
    "device_tracker": DomainSpec(),
}


class LegacyZoneTrigger(Trigger):
    """Legacy zone trigger (platform: zone)."""

    @classmethod
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config, migrating legacy format to options."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _LEGACY_OPTIONS_SCHEMA
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        config = cast(ConfigType, _LEGACY_TRIGGER_OPTIONS_SCHEMA(config))
        registry = er.async_get(hass)
        config[CONF_OPTIONS][CONF_ENTITY_ID] = er.async_validate_entity_ids(
            registry, config[CONF_OPTIONS][CONF_ENTITY_ID]
        )
        return config

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._options = config.options

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Listen for state changes based on configuration."""
        entity_id: list[str] = self._options[CONF_ENTITY_ID]
        zone_entity_id: str = self._options[CONF_ZONE]
        event: str = self._options[CONF_EVENT]

        @callback
        def zone_automation_listener(zone_event: Event[EventStateChangedData]) -> None:
            """Listen for state changes and calls action."""
            entity = zone_event.data["entity_id"]
            from_s = zone_event.data["old_state"]
            to_s = zone_event.data["new_state"]

            if (from_s and not _state_has_zone_info(from_s)) or (
                to_s and not _state_has_zone_info(to_s)
            ):
                return

            if not (zone_state := self._hass.states.get(zone_entity_id)):
                _LOGGER.warning(
                    "Non-existing zone '%s' in a zone trigger",
                    zone_entity_id,
                )
                return

            from_match = (
                condition.zone(self._hass, zone_state, from_s) if from_s else False
            )
            to_match = condition.zone(self._hass, zone_state, to_s) if to_s else False

            if (event == EVENT_ENTER and not from_match and to_match) or (
                event == EVENT_LEAVE and from_match and not to_match
            ):
                description = f"{entity} {_EVENT_DESCRIPTION[event]} {zone_state.attributes[EntityStateAttribute.FRIENDLY_NAME]}"
                run_action(
                    {
                        "entity_id": entity,
                        "from_state": from_s,
                        "to_state": to_s,
                        "zone": zone_state,
                        "event": event,
                    },
                    description,
                    to_s.context if to_s else None,
                )

        return async_track_state_change_event(
            self._hass, entity_id, zone_automation_listener
        )


class ZoneTriggerBase(EntityTriggerBase):
    """Base for zone-based triggers targeting person and device_tracker entities."""

    _domain_specs = _DOMAIN_SPECS
    _schema = _ZONE_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._zone: str = self._options[CONF_ZONE]

    def _in_target_zone(self, state: State) -> bool:
        """Check if the entity is in the selected zone."""
        if (in_zones_attr := get_in_zones_attribute(state)) and (
            in_zones := state.attributes.get(in_zones_attr)
        ):
            return self._zone in in_zones
        return False


class EnteredZoneTrigger(ZoneTriggerBase):
    """Trigger when an entity enters the selected zone."""

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the entity was not already in the selected zone."""
        return not self._in_target_zone(from_state)

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check that the entity is now in the selected zone."""
        return self._in_target_zone(state)


class LeftZoneTrigger(ZoneTriggerBase):
    """Trigger when an entity leaves the selected zone."""

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the entity was previously in the selected zone."""
        return self._in_target_zone(from_state)

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check that the entity is no longer in the selected zone."""
        return not self._in_target_zone(state)


_OCCUPANCY_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default={}): {
            vol.Required(CONF_ZONE): cv.entity_domain(DOMAIN),
            vol.Optional(CONF_FOR): cv.positive_time_period,
        },
    }
)


class _ZoneOccupancyTriggerBase(EntityTriggerBase):
    """Base for zone occupancy triggers (single zone, no behavior)."""

    _domain_specs = {"zone": DomainSpec()}
    _schema = _OCCUPANCY_TRIGGER_SCHEMA

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config and synthesize a target from the zone option.

        We synthesize a target because we allow users to pick a single zone
        to monitor, not a target.
        """
        config = cast(ConfigType, cls._schema(config))
        config[CONF_TARGET] = {CONF_ENTITY_ID: [config[CONF_OPTIONS][CONF_ZONE]]}
        return config

    @staticmethod
    def _occupancy_count(state: State) -> int | None:
        """Return the zone's persons-in-zone count; None if unparsable."""
        try:
            return int(state.state)
        except TypeError, ValueError:
            return None

    @classmethod
    def _is_occupied(cls, state: State) -> bool:
        """Return True if the zone has at least one occupant."""
        count = cls._occupancy_count(state)
        return count is not None and count >= 1


class OccupancyDetectedTrigger(_ZoneOccupancyTriggerBase):
    """Trigger when a zone transitions to an occupied state."""

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check that the zone is occupied."""
        return self._is_occupied(state)

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the zone was previously not occupied."""
        return not self._is_occupied(from_state)


class OccupancyClearedTrigger(_ZoneOccupancyTriggerBase):
    """Trigger when a zone transitions from occupied to unoccupied."""

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check that the zone is empty (count == 0)."""
        return self._occupancy_count(state) == 0

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the zone was previously occupied."""
        return self._is_occupied(from_state)


TRIGGERS: dict[str, type[Trigger]] = {
    "_": LegacyZoneTrigger,
    "entered": EnteredZoneTrigger,
    "left": LeftZoneTrigger,
    "occupancy_detected": OccupancyDetectedTrigger,
    "occupancy_cleared": OccupancyClearedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for zones."""
    return TRIGGERS
