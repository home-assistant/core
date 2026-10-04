"""Platform allowing several automations to be grouped into one automation."""

from typing import Any, override

from propcache.api import cached_property

from homeassistant.components.automation import (
    ATTR_VARIABLES,
    CONF_SKIP_CONDITION,
    CONF_STOP_ACTIONS,
    DOMAIN as AUTOMATION_DOMAIN,
    SERVICE_TRIGGER,
    BaseAutomationEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.script import ScriptRunResult

from .entity import GroupEntity

CONF_ALL = "all"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Automation Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            AutomationGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
                config_entry.options.get(CONF_ALL),
            )
        ]
    )


@callback
def async_create_preview_automation(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> AutomationGroup:
    """Create a preview automation group."""
    return AutomationGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
        validated_config.get(CONF_ALL, False),
    )


# pylint: disable-next=home-assistant-enforce-class-module
class AutomationGroup(GroupEntity, BaseAutomationEntity):
    """Representation of an automation group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
        mode: bool | None,
    ) -> None:
        """Initialize an automation group."""
        self._entity_ids = entity_ids

        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self.raw_config = None
        self.mode = any
        if mode:
            self.mode = all

    @cached_property
    @override
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""
        return set()

    @cached_property
    @override
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced floors."""
        return set()

    @cached_property
    @override
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        return set()

    @property
    @override
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        return None

    @cached_property
    @override
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        return set()

    @cached_property
    @override
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        return set(self._entity_ids)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to all automations in the group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        await self.hass.services.async_call(
            AUTOMATION_DOMAIN,
            SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to all automations in the group."""
        data: dict[str, Any] = {ATTR_ENTITY_ID: self._entity_ids}
        if CONF_STOP_ACTIONS in kwargs:
            data[CONF_STOP_ACTIONS] = kwargs[CONF_STOP_ACTIONS]
        await self.hass.services.async_call(
            AUTOMATION_DOMAIN,
            SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    @override
    async def async_trigger(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
        skip_condition: bool = False,
    ) -> ScriptRunResult | None:
        """Forward the trigger command to all automations in the group."""
        await self.hass.services.async_call(
            AUTOMATION_DOMAIN,
            SERVICE_TRIGGER,
            {
                ATTR_ENTITY_ID: self._entity_ids,
                ATTR_VARIABLES: run_variables,
                CONF_SKIP_CONDITION: skip_condition,
            },
            blocking=True,
            context=context or self._context,
        )
        return None

    @callback
    @override
    def async_update_group_state(self) -> None:
        """Query all members and determine the automation group state."""
        states = [
            state.state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        valid_state = self.mode(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        if not valid_state:
            # Set as unknown if any / all member is unknown or unavailable
            self._attr_is_on = None
        else:
            # Set as ON if any / all member is ON
            self._attr_is_on = self.mode(state == STATE_ON for state in states)

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)
