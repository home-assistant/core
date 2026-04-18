"""Provides conditions for selects."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.input_select import DOMAIN as INPUT_SELECT_DOMAIN
from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    ConditionConfig,
    EntityStateConditionBase,
)

from .const import CONF_OPTION, DOMAIN

IS_OPTION_SELECTED_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_OPTION): vol.All(
                cv.ensure_list, vol.Length(min=1), [str]
            ),
        },
    }
)

SELECT_DOMAIN_SPECS = {DOMAIN: DomainSpec(), INPUT_SELECT_DOMAIN: DomainSpec()}


class IsOptionSelectedCondition(EntityStateConditionBase):
    """Condition for select option."""

    _domain_specs = SELECT_DOMAIN_SPECS
    _schema = IS_OPTION_SELECTED_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the option selected condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._states = set(config.options[CONF_OPTION])


CONDITIONS: dict[str, type[Condition]] = {
    "is_option_selected": IsOptionSelectedCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the select conditions."""
    return CONDITIONS
