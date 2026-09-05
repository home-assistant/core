"""Provide infrared automation triggers."""

from typing import TYPE_CHECKING, Any, Final, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CODE,
    CONF_COMMAND,
    CONF_NAME,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .code import code_to_frame, frames_match, signal_to_frame
from .const import DOMAIN
from .entity import SIGNAL_INFRARED_RECEIVED, InfraredReceivedSignal

CONF_COMMANDS: Final = "commands"


def _code(value: Any) -> str:
    """Validate an infrared code."""
    code = cv.string(value)
    try:
        code_to_frame(code)
    except ValueError as err:
        raise vol.Invalid(f"Invalid infrared code: {err}") from err
    return code


_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): vol.All(cv.string, vol.Length(min=1)),
        vol.Required(CONF_CODE): _code,
    }
)

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_COMMANDS): vol.All([_COMMAND_SCHEMA], vol.Length(min=1)),
        },
    }
)


class _ReceiverTracker(TargetEntityChangeTracker):
    """Tracks the infrared entities the trigger's target resolves to."""

    def __init__(self, hass: HomeAssistant, target_selection: TargetSelection) -> None:
        """Initialize the tracker."""

        def entity_filter(entities: set[str]) -> set[str]:
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        super().__init__(hass, target_selection, entity_filter)
        self.entity_ids: set[str] = set()

    @callback
    @override
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Store the new entity set."""
        self.entity_ids = tracked_entities


class CommandReceivedTrigger(Trigger):
    """Trigger for infrared commands received by a receiver."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
            assert config.options is not None
        self._target = config.target
        self._commands: list[tuple[str, list[int]]] = [
            (command[CONF_NAME], code_to_frame(command[CONF_CODE]))
            for command in config.options[CONF_COMMANDS]
        ]

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        target_selection = TargetSelection(self._target)
        if not target_selection.has_any_target:
            raise HomeAssistantError(f"No target defined in {self._target}")
        tracker = _ReceiverTracker(self._hass, target_selection)

        @callback
        def async_signal_received(
            entity_id: str, signal: InfraredReceivedSignal
        ) -> None:
            """Run the action for the first configured command that matches."""
            if entity_id not in tracker.entity_ids:
                return
            frame = signal_to_frame(signal)
            for name, expected_frame in self._commands:
                if frames_match(frame, expected_frame):
                    run_action(
                        {ATTR_ENTITY_ID: entity_id, CONF_COMMAND: name},
                        f"infrared command {name} received by {entity_id}",
                    )
                    return

        remove_tracker = await tracker.async_setup()
        remove_dispatcher = async_dispatcher_connect(
            self._hass, SIGNAL_INFRARED_RECEIVED, async_signal_received
        )

        @callback
        def async_remove() -> None:
            """Detach the trigger."""
            remove_dispatcher()
            remove_tracker()

        return async_remove


TRIGGERS: dict[str, type[Trigger]] = {
    "_": CommandReceivedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for infrared."""
    return TRIGGERS
