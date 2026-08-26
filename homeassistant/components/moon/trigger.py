"""Provides triggers for the moon."""

from datetime import datetime
from typing import cast, override

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PHASE
from .helpers import MOON_PHASES, moon_phase

PHASE_ANY = "any"

_PHASE_CHANGED_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_PHASE, default=PHASE_ANY): vol.In(
                [PHASE_ANY, *MOON_PHASES]
            ),
        }
    }
)


class MoonPhaseChangedTrigger(Trigger):
    """Trigger that fires when the moon enters a new phase."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _PHASE_CHANGED_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options = config.options or {}
        self._phase: str = options[CONF_PHASE]

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        last_phase = moon_phase()

        @callback
        def check_phase(_now: datetime) -> None:
            nonlocal last_phase
            current_phase = moon_phase()
            if current_phase == last_phase:
                return
            previous_phase = last_phase
            last_phase = current_phase
            if self._phase in (PHASE_ANY, current_phase):
                run_action(
                    {"phase": current_phase, "previous_phase": previous_phase},
                    "moon phase changed",
                )

        # The binned phase can only change when the local date rolls over.
        return async_track_time_change(
            self._hass, check_phase, hour=0, minute=0, second=0
        )


TRIGGERS: dict[str, type[Trigger]] = {
    "phase_changed": MoonPhaseChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for the moon."""
    return TRIGGERS
