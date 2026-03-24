"""Provides conditions for texts."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.input_text import DOMAIN as INPUT_TEXT_DOMAIN
from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    Condition,
    ConditionConfig,
    EntityConditionBase,
)

from .const import DOMAIN

CONF_VALUE = "value"

_TEXT_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_ANY, BEHAVIOR_ALL]
            ),
            vol.Required(CONF_VALUE): cv.string,
        },
    }
)


class TextIsEqualToCondition(EntityConditionBase):
    """Condition for text entity value matching."""

    _domain_specs = {
        DOMAIN: DomainSpec(),
        INPUT_TEXT_DOMAIN: DomainSpec(),
    }
    _schema = _TEXT_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options
        self._value: str = config.options[CONF_VALUE]

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state matches the expected value."""
        return entity_state.state == self._value


CONDITIONS: dict[str, type[Condition]] = {
    "is_equal_to": TextIsEqualToCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the text conditions."""
    return CONDITIONS
