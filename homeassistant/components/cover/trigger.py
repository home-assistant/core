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

CONF_LOWER = "lower"
CONF_UPPER = "upper"
CONF_ABOVE = "above"
CONF_BELOW = "below"
CONF_FULLY_OPENED = "fully_opened"
CONF_FULLY_CLOSED = "fully_closed"

OPENS_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Optional(CONF_FULLY_OPENED, default=False): cv.boolean,
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

CLOSES_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Optional(CONF_FULLY_CLOSED, default=False): cv.boolean,
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

STOPS_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {},
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

POSITION_CHANGED_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPTIONS, default={}): {
            vol.Exclusive(CONF_LOWER, "position_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Exclusive(CONF_UPPER, "position_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Exclusive(CONF_ABOVE, "position_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Exclusive(CONF_BELOW, "position_range"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class CoverOpensTriggerBase(Trigger):
    """Base trigger for when a cover opens."""

    device_class: CoverDeviceClass

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

            # Filter by device class
            device_class = to_state.attributes.get(CONF_DEVICE_CLASS)
            if device_class != self.device_class:
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
                    f"{self.device_class} opened on {entity_id}",
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


class CoverClosesTriggerBase(Trigger):
    """Base trigger for when a cover closes."""

    device_class: CoverDeviceClass

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

            # Filter by device class
            device_class = to_state.attributes.get(CONF_DEVICE_CLASS)
            if device_class != self.device_class:
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
                    f"{self.device_class} closed on {entity_id}",
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


class CoverStopsTriggerBase(Trigger):
    """Base trigger for when a cover stops moving."""

    device_class: CoverDeviceClass

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, STOPS_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the cover stops trigger."""
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

            # Filter by device class
            device_class = to_state.attributes.get(CONF_DEVICE_CLASS)
            if device_class != self.device_class:
                return

            # Trigger when cover stops (from opening/closing to open/closed)
            if from_state and from_state.state in (
                CoverState.OPENING,
                CoverState.CLOSING,
            ):
                if to_state.state in (CoverState.OPEN, CoverState.CLOSED):
                    run_action(
                        {
                            ATTR_ENTITY_ID: entity_id,
                            "from_state": from_state,
                            "to_state": to_state,
                        },
                        f"{self.device_class} stopped on {entity_id}",
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


class CoverPositionChangedTriggerBase(Trigger):
    """Base trigger for when a cover's position changes."""

    device_class: CoverDeviceClass

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, POSITION_CHANGED_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the cover position changed trigger."""
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

            # Filter by device class
            device_class = to_state.attributes.get(CONF_DEVICE_CLASS)
            if device_class != self.device_class:
                return

            # Get position values
            from_position = (
                from_state.attributes.get(ATTR_CURRENT_POSITION) if from_state else None
            )
            to_position = to_state.attributes.get(ATTR_CURRENT_POSITION)

            # Only trigger if position value exists and has changed
            if to_position is None or from_position == to_position:
                return

            # Apply threshold filters if configured
            if lower_limit is not None and to_position < lower_limit:
                return
            if upper_limit is not None and to_position > upper_limit:
                return
            if above_limit is not None and to_position <= above_limit:
                return
            if below_limit is not None and to_position >= below_limit:
                return

            run_action(
                {
                    ATTR_ENTITY_ID: entity_id,
                    "from_state": from_state,
                    "to_state": to_state,
                    "from_position": from_position,
                    "to_position": to_position,
                },
                f"{self.device_class} position changed on {entity_id}",
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


# Device-class-specific trigger classes for curtain
class CurtainOpensTrigger(CoverOpensTriggerBase):
    """Trigger for when a curtain opens."""

    device_class = CoverDeviceClass.CURTAIN


class CurtainClosesTrigger(CoverClosesTriggerBase):
    """Trigger for when a curtain closes."""

    device_class = CoverDeviceClass.CURTAIN


class CurtainStopsTrigger(CoverStopsTriggerBase):
    """Trigger for when a curtain stops moving."""

    device_class = CoverDeviceClass.CURTAIN


class CurtainPositionChangedTrigger(CoverPositionChangedTriggerBase):
    """Trigger for when a curtain's position changes."""

    device_class = CoverDeviceClass.CURTAIN


# Device-class-specific trigger classes for shutter
class ShutterOpensTrigger(CoverOpensTriggerBase):
    """Trigger for when a shutter opens."""

    device_class = CoverDeviceClass.SHUTTER


class ShutterClosesTrigger(CoverClosesTriggerBase):
    """Trigger for when a shutter closes."""

    device_class = CoverDeviceClass.SHUTTER


class ShutterStopsTrigger(CoverStopsTriggerBase):
    """Trigger for when a shutter stops moving."""

    device_class = CoverDeviceClass.SHUTTER


class ShutterPositionChangedTrigger(CoverPositionChangedTriggerBase):
    """Trigger for when a shutter's position changes."""

    device_class = CoverDeviceClass.SHUTTER


# Device-class-specific trigger classes for blind
class BlindOpensTrigger(CoverOpensTriggerBase):
    """Trigger for when a blind opens."""

    device_class = CoverDeviceClass.BLIND


class BlindClosesTrigger(CoverClosesTriggerBase):
    """Trigger for when a blind closes."""

    device_class = CoverDeviceClass.BLIND


class BlindStopsTrigger(CoverStopsTriggerBase):
    """Trigger for when a blind stops moving."""

    device_class = CoverDeviceClass.BLIND


class BlindPositionChangedTrigger(CoverPositionChangedTriggerBase):
    """Trigger for when a blind's position changes."""

    device_class = CoverDeviceClass.BLIND


TRIGGERS: dict[str, type[Trigger]] = {
    "curtain_opens": CurtainOpensTrigger,
    "curtain_closes": CurtainClosesTrigger,
    "curtain_stops": CurtainStopsTrigger,
    "curtain_position_changed": CurtainPositionChangedTrigger,
    "shutter_opens": ShutterOpensTrigger,
    "shutter_closes": ShutterClosesTrigger,
    "shutter_stops": ShutterStopsTrigger,
    "shutter_position_changed": ShutterPositionChangedTrigger,
    "blind_opens": BlindOpensTrigger,
    "blind_closes": BlindClosesTrigger,
    "blind_stops": BlindStopsTrigger,
    "blind_position_changed": BlindPositionChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for covers."""
    return TRIGGERS
