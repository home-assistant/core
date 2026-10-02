"""Offer Home Assistant system state conditions."""

from typing import Unpack, cast, override

import probatio

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import system_state
from homeassistant.helpers.condition import Condition, ConditionCheckParams
from homeassistant.helpers.typing import ConfigType

_SYSTEM_STATE_CONDITION_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_OPTIONS, default=dict): {}}
)


class _SystemStateCondition(Condition):
    """Base class for the option-less system state conditions."""

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _SYSTEM_STATE_CONDITION_SCHEMA(config))


class RestartRequiredCondition(_SystemStateCondition):
    """Test if Home Assistant needs a restart."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return system_state.async_get(self._hass).home_assistant_restart_required


class HostRebootRequiredCondition(_SystemStateCondition):
    """Test if the host needs a reboot."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return system_state.async_get(self._hass).host_reboot_required


CONDITIONS: dict[str, type[Condition]] = {
    "host_reboot_required": HostRebootRequiredCondition,
    "restart_required": RestartRequiredCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the Home Assistant conditions."""
    return CONDITIONS
