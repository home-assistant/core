"""Provides triggers for climate."""

from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_HVAC_ACTION, ATTR_HVAC_MODE, DOMAIN, HVAC_MODES, HVACMode

CLIMATE_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {},
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

MODE_CHANGED_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Optional(ATTR_HVAC_MODE, default=[]): vol.All(
                cv.ensure_list, [vol.In(HVAC_MODES)]
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class ClimateTurnsOnTrigger(Trigger):
    """Trigger for when a climate turns on."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, CLIMATE_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the climate turns on trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
            assert config.target is not None
        self._options = config.options
        self._target = config.target

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # Ignore unavailable states
            if to_state is None or to_state.state == STATE_UNAVAILABLE:
                return

            # Check if climate turned on (from off to any other mode)
            if (
                from_state is not None
                and from_state.state == HVACMode.OFF
                and to_state.state != HVACMode.OFF
            ):
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"climate {entity_id} turned on",
                    event.context,
                )

        def entity_filter(entities: set[str]) -> set[str]:
            """Filter entities of this domain."""
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, entity_filter
        )


class ClimateTurnsOffTrigger(Trigger):
    """Trigger for when a climate turns off."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, CLIMATE_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the climate turns off trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
            assert config.target is not None
        self._options = config.options
        self._target = config.target

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # Ignore unavailable states
            if to_state is None or to_state.state == STATE_UNAVAILABLE:
                return

            # Check if climate turned off (from any mode to off)
            if (
                from_state is not None
                and from_state.state != HVACMode.OFF
                and to_state.state == HVACMode.OFF
            ):
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"climate {entity_id} turned off",
                    event.context,
                )

        def entity_filter(entities: set[str]) -> set[str]:
            """Filter entities of this domain."""
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, entity_filter
        )


class ClimateModeChangedTrigger(Trigger):
    """Trigger for when a climate mode changes."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, MODE_CHANGED_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the climate mode changed trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
            assert config.target is not None
        self._options = config.options
        self._target = config.target

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        hvac_modes_filter = self._options[ATTR_HVAC_MODE]

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # Ignore unavailable states
            if to_state is None or to_state.state == STATE_UNAVAILABLE:
                return

            # Check if hvac_mode changed
            if from_state is not None and from_state.state != to_state.state:
                # If hvac_modes filter is specified, check if the new mode matches
                if hvac_modes_filter and to_state.state not in hvac_modes_filter:
                    return

                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"climate {entity_id} mode changed to {to_state.state}",
                    event.context,
                )

        def entity_filter(entities: set[str]) -> set[str]:
            """Filter entities of this domain."""
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, entity_filter
        )


class ClimateCoolingTrigger(Trigger):
    """Trigger for when a climate starts cooling."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, CLIMATE_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the climate cooling trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
            assert config.target is not None
        self._options = config.options
        self._target = config.target

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # Ignore unavailable states
            if to_state is None or to_state.state == STATE_UNAVAILABLE:
                return

            # Check if climate started cooling
            from_action = from_state.attributes.get(ATTR_HVAC_ACTION) if from_state else None
            to_action = to_state.attributes.get(ATTR_HVAC_ACTION)

            if from_action != "cooling" and to_action == "cooling":
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"climate {entity_id} started cooling",
                    event.context,
                )

        def entity_filter(entities: set[str]) -> set[str]:
            """Filter entities of this domain."""
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, entity_filter
        )


class ClimateHeatingTrigger(Trigger):
    """Trigger for when a climate starts heating."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, CLIMATE_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the climate heating trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
            assert config.target is not None
        self._options = config.options
        self._target = config.target

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            # Ignore unavailable states
            if to_state is None or to_state.state == STATE_UNAVAILABLE:
                return

            # Check if climate started heating
            from_action = from_state.attributes.get(ATTR_HVAC_ACTION) if from_state else None
            to_action = to_state.attributes.get(ATTR_HVAC_ACTION)

            if from_action != "heating" and to_action == "heating":
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"climate {entity_id} started heating",
                    event.context,
                )

        def entity_filter(entities: set[str]) -> set[str]:
            """Filter entities of this domain."""
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, entity_filter
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "turns_on": ClimateTurnsOnTrigger,
    "turns_off": ClimateTurnsOffTrigger,
    "mode_changed": ClimateModeChangedTrigger,
    "cooling": ClimateCoolingTrigger,
    "heating": ClimateHeatingTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climate."""
    return TRIGGERS
