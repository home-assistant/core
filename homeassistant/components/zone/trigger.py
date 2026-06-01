"""Offer zone automation rules."""

import logging
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.components.device_tracker import ATTR_IN_ZONES
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_OPTIONS,
    CONF_ZONE,
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
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
)
from homeassistant.helpers.typing import ConfigType

from . import condition

EVENT_ENTER = "enter"
EVENT_LEAVE = "leave"
DEFAULT_EVENT = EVENT_ENTER

_LOGGER = logging.getLogger(__name__)

_EVENT_DESCRIPTION = {EVENT_ENTER: "entering", EVENT_LEAVE: "leaving"}

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
            vol.Required(CONF_ZONE): cv.entity_domain("zone"),
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
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config, migrating legacy format to options."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _LEGACY_OPTIONS_SCHEMA
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
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

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
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

            if (from_s and not location.has_location(from_s)) or (
                to_s and not location.has_location(to_s)
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
                description = f"{entity} {_EVENT_DESCRIPTION[event]} {zone_state.attributes[ATTR_FRIENDLY_NAME]}"
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
        in_zones = state.attributes.get(ATTR_IN_ZONES) or ()
        return self._zone in in_zones


class EnteredZoneTrigger(ZoneTriggerBase):
    """Trigger when an entity enters the selected zone."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the entity was not already in the selected zone."""
        return not self._in_target_zone(from_state)

    def is_valid_state(self, state: State) -> bool:
        """Check that the entity is now in the selected zone."""
        return self._in_target_zone(state)


class LeftZoneTrigger(ZoneTriggerBase):
    """Trigger when an entity leaves the selected zone."""

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the entity was previously in the selected zone."""
        return self._in_target_zone(from_state)

    def is_valid_state(self, state: State) -> bool:
        """Check that the entity is no longer in the selected zone."""
        return not self._in_target_zone(state)


TRIGGERS: dict[str, type[Trigger]] = {
    "_": LegacyZoneTrigger,
    "entered": EnteredZoneTrigger,
    "left": LeftZoneTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for zones."""
    return TRIGGERS
