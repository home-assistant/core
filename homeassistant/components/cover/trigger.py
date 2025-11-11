"""Provides triggers for covers."""

from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
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

from . import ATTR_CURRENT_POSITION, CoverDeviceClass, CoverState
from .const import DOMAIN

CONF_FULLY_OPENED = "fully_opened"
CONF_FULLY_CLOSED = "fully_closed"

OPENS_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Optional(CONF_FULLY_OPENED, default=False): cv.boolean,
            vol.Optional(CONF_DEVICE_CLASS, default=[]): vol.All(
                cv.ensure_list, [vol.Coerce(CoverDeviceClass)]
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

CLOSES_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Optional(CONF_FULLY_CLOSED, default=False): cv.boolean,
            vol.Optional(CONF_DEVICE_CLASS, default=[]): vol.All(
                cv.ensure_list, [vol.Coerce(CoverDeviceClass)]
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class CoverOpensTrigger(Trigger):
    """Trigger for when a cover opens."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, OPENS_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the cover opens trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
            assert config.options is not None
        self._target = config.target
        self._options = config.options

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        fully_opened = self._options[CONF_FULLY_OPENED]
        device_classes_filter = self._options[CONF_DEVICE_CLASS]

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

            # Filter by device class if specified
            if device_classes_filter:
                device_class = to_state.attributes.get(CONF_DEVICE_CLASS)
                if device_class not in device_classes_filter:
                    return

            # Trigger when cover opens or is opening
            if to_state.state in (CoverState.OPEN, CoverState.OPENING):
                # If fully_opened is True, only trigger when position reaches 100
                if fully_opened:
                    current_position = to_state.attributes.get(ATTR_CURRENT_POSITION)
                    if current_position != 100:
                        return

                # Only trigger on state change, not if already in that state
                if from_state and from_state.state == to_state.state:
                    # For fully_opened, allow triggering when position changes to 100
                    if fully_opened:
                        from_position = from_state.attributes.get(ATTR_CURRENT_POSITION)
                        to_position = to_state.attributes.get(ATTR_CURRENT_POSITION)
                        if from_position == to_position:
                            return
                    else:
                        return

                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"cover opened on {entity_id}",
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


class CoverClosesTrigger(Trigger):
    """Trigger for when a cover closes."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, CLOSES_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the cover closes trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
            assert config.options is not None
        self._target = config.target
        self._options = config.options

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        fully_closed = self._options[CONF_FULLY_CLOSED]
        device_classes_filter = self._options[CONF_DEVICE_CLASS]

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

            # Filter by device class if specified
            if device_classes_filter:
                device_class = to_state.attributes.get(CONF_DEVICE_CLASS)
                if device_class not in device_classes_filter:
                    return

            # Trigger when cover closes or is closing
            if to_state.state in (CoverState.CLOSED, CoverState.CLOSING):
                # If fully_closed is True, only trigger when position reaches 0
                if fully_closed:
                    current_position = to_state.attributes.get(ATTR_CURRENT_POSITION)
                    if current_position != 0:
                        return

                # Only trigger on state change, not if already in that state
                if from_state and from_state.state == to_state.state:
                    # For fully_closed, allow triggering when position changes to 0
                    if fully_closed:
                        from_position = from_state.attributes.get(ATTR_CURRENT_POSITION)
                        to_position = to_state.attributes.get(ATTR_CURRENT_POSITION)
                        if from_position == to_position:
                            return
                    else:
                        return

                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                    },
                    f"cover closed on {entity_id}",
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
    "opens": CoverOpensTrigger,
    "closes": CoverClosesTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for covers."""
    return TRIGGERS
