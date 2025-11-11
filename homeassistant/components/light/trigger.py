"""Provides triggers for lights."""

from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
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

from .const import DOMAIN

ATTR_BRIGHTNESS = "brightness"
CONF_LOWER = "lower"
CONF_UPPER = "upper"
CONF_ABOVE = "above"
CONF_BELOW = "below"

TURNS_ON_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

TURNS_OFF_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

BRIGHTNESS_CHANGED_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Exclusive(CONF_LOWER, "brightness_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
            vol.Exclusive(CONF_UPPER, "brightness_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
            vol.Exclusive(CONF_ABOVE, "brightness_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
            vol.Exclusive(CONF_BELOW, "brightness_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class LightTurnsOnTrigger(Trigger):
    """Trigger for when a light turns on."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, TURNS_ON_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the light turns on trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
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

            # Trigger when light turns on (from off to on)
            if from_state and from_state.state == STATE_OFF and to_state.state == STATE_ON:
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"light turned on on {entity_id}",
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


class LightTurnsOffTrigger(Trigger):
    """Trigger for when a light turns off."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, TURNS_OFF_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the light turns off trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
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

            # Trigger when light turns off (from on to off)
            if from_state and from_state.state == STATE_ON and to_state.state == STATE_OFF:
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"light turned off on {entity_id}",
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


class LightBrightnessChangedTrigger(Trigger):
    """Trigger for when a light's brightness changes."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, BRIGHTNESS_CHANGED_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the light brightness changed trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._target = config.target
        self._options = config.options or {}

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        lower_limit = self._options.get(CONF_LOWER)
        upper_limit = self._options.get(CONF_UPPER)
        above_limit = self._options.get(CONF_ABOVE)
        below_limit = self._options.get(CONF_BELOW)

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

            # Get brightness values
            from_brightness = (
                from_state.attributes.get(ATTR_BRIGHTNESS) if from_state else None
            )
            to_brightness = to_state.attributes.get(ATTR_BRIGHTNESS)

            # Only trigger if brightness value exists and has changed
            if to_brightness is None or from_brightness == to_brightness:
                return

            # Apply threshold filters if configured
            if lower_limit is not None and to_brightness < lower_limit:
                return
            if upper_limit is not None and to_brightness > upper_limit:
                return
            if above_limit is not None and to_brightness <= above_limit:
                return
            if below_limit is not None and to_brightness >= below_limit:
                return

            run_action(
                {
                    ATTR_ENTITY_ID: entity_id,
                    "from_state": from_state,
                    "to_state": to_state,
                    "from_brightness": from_brightness,
                    "to_brightness": to_brightness,
                },
                f"brightness changed on {entity_id}",
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
    "turns_on": LightTurnsOnTrigger,
    "turns_off": LightTurnsOffTrigger,
    "brightness_changed": LightBrightnessChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
