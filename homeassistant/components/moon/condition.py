"""Offer moon phase based conditions."""

from typing import Unpack, cast, override

import probatio

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PHASE
from .helpers import MOON_PHASES, MoonData, async_get_moon_data, is_waxing, moon_phase

_STATE_CONDITION_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_OPTIONS, default=dict): {}}
)
_IS_PHASE_CONDITION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS, default=dict): {
            probatio.Required(CONF_PHASE): probatio.In(MOON_PHASES),
        }
    }
)


class _MoonCondition(Condition):
    """Base class for moon conditions that use the shared moon data."""

    _moon_data: MoonData

    @override
    async def _async_setup(self) -> None:
        """Load the shared moon data."""
        try:
            self._moon_data = await async_get_moon_data(self._hass)
        except OSError as err:
            raise HomeAssistantError("Unable to load the moon ephemeris") from err


class _MoonStateCondition(_MoonCondition):
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
        return is_waxing(self._moon_data)


class _WaningCondition(_MoonStateCondition):
    """Test if the moon is waning."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return not is_waxing(self._moon_data)


class _IsPhaseCondition(_MoonCondition):
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
        return moon_phase(self._moon_data) == self._phase


CONDITIONS: dict[str, type[Condition]] = {
    "is_phase": _IsPhaseCondition,
    "is_waxing": _WaxingCondition,
    "is_waning": _WaningCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the moon conditions."""
    return CONDITIONS
