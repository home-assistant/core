"""Provides triggers for the moon."""

from datetime import datetime, timedelta
from typing import cast, override

import probatio

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PHASE
from .helpers import MOON_PHASES, async_get_moon_data, moon_phase

PHASE_ANY = "any"

# Phase boundaries fall at half-days, so checking intraday catches each change promptly.
_CHECK_INTERVAL = timedelta(hours=1)

_PHASE_CHANGED_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS, default=dict): {
            probatio.Optional(CONF_PHASE, default=PHASE_ANY): probatio.In(
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
        try:
            moon_data = await async_get_moon_data(self._hass)
        except OSError as err:
            raise HomeAssistantError("Unable to load the moon ephemeris") from err
        last_phase = moon_phase(moon_data)

        @callback
        def check_phase(_now: datetime) -> None:
            nonlocal last_phase
            current_phase = moon_phase(moon_data)
            if current_phase == last_phase:
                return
            previous_phase = last_phase
            last_phase = current_phase
            if self._phase in (PHASE_ANY, current_phase):
                run_action(
                    {"phase": current_phase, "previous_phase": previous_phase},
                    "moon phase changed",
                )

        return async_track_time_interval(self._hass, check_phase, _CHECK_INTERVAL)


TRIGGERS: dict[str, type[Trigger]] = {
    "phase_changed": MoonPhaseChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for the moon."""
    return TRIGGERS
