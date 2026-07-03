"""Offer moon phase based conditions."""

from typing import Unpack, cast, override

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.moon import MOON_PHASES, is_waxing, moon_phase
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PHASE

_STATE_CONDITION_SCHEMA = vol.Schema({vol.Required(CONF_OPTIONS, default=dict): {}})
_IS_PHASE_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Required(CONF_PHASE): vol.In(MOON_PHASES),
        }
    }
)


class _MoonStateCondition(Condition):
    """Base class for the option-less moon phase conditions."""

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _STATE_CONDITION_SCHEMA(config))


class _WaxingCondition(_MoonStateCondition):
    """Test if the moon is waxing."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return is_waxing()


class _WaningCondition(_MoonStateCondition):
    """Test if the moon is waning."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return not is_waxing()


class _IsPhaseCondition(Condition):
    """Test if the moon is in a specific phase."""

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _IS_PHASE_CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._phase: str = config.options[CONF_PHASE]

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return moon_phase() == self._phase


CONDITIONS: dict[str, type[Condition]] = {
    "is_phase": _IsPhaseCondition,
    "is_waxing": _WaxingCondition,
    "is_waning": _WaningCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the moon conditions."""
    return CONDITIONS
