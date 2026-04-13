"""Provides conditions for humidifiers."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import ATTR_MODE, CONF_OPTIONS, PERCENTAGE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    ConditionConfig,
    EntityStateConditionBase,
    make_entity_numerical_condition,
    make_entity_state_condition,
)
from homeassistant.helpers.entity import get_supported_features

from .const import (
    ATTR_ACTION,
    ATTR_HUMIDITY,
    DOMAIN,
    HumidifierAction,
    HumidifierEntityFeature,
)

CONF_MODE = "mode"

IS_MODE_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_MODE): vol.All(cv.ensure_list, vol.Length(min=1), [str]),
        },
    }
)


def _supports_feature(hass: HomeAssistant, entity_id: str, features: int) -> bool:
    """Test if an entity supports the specified features."""
    try:
        return bool(get_supported_features(hass, entity_id) & features)
    except HomeAssistantError:
        return False


class IsModeCondition(EntityStateConditionBase):
    """Condition for humidifier mode."""

    _domain_specs = {DOMAIN: DomainSpec(value_source=ATTR_MODE)}
    _schema = IS_MODE_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the mode condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._states = set(config.options[CONF_MODE])

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if _supports_feature(self._hass, entity_id, HumidifierEntityFeature.MODES)
        }


CONDITIONS: dict[str, type[Condition]] = {
    "is_off": make_entity_state_condition(DOMAIN, STATE_OFF),
    "is_on": make_entity_state_condition(DOMAIN, STATE_ON),
    "is_drying": make_entity_state_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_ACTION)}, HumidifierAction.DRYING
    ),
    "is_humidifying": make_entity_state_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_ACTION)}, HumidifierAction.HUMIDIFYING
    ),
    "is_mode": IsModeCondition,
    "is_target_humidity": make_entity_numerical_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_HUMIDITY)},
        valid_unit=PERCENTAGE,
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the humidifier conditions."""
    return CONDITIONS
