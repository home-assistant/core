"""Provide infrared automation conditions."""

from typing import TYPE_CHECKING, Unpack, cast, override

import voluptuous as vol

from homeassistant.const import CONF_COMMAND, CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.typing import ConfigType

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_COMMAND): vol.All(
                [vol.All(cv.string, vol.Length(min=1))], vol.Length(min=1)
            ),
        }
    }
)


class CommandCondition(Condition):
    """Test which infrared command started the automation."""

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._commands: set[str] = set(config.options[CONF_COMMAND])

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        variables = kwargs.get("variables")
        if variables is None or (trigger := variables.get("trigger")) is None:
            return False
        return trigger.get(CONF_COMMAND) in self._commands


CONDITIONS: dict[str, type[Condition]] = {
    "_": CommandCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for infrared."""
    return CONDITIONS
