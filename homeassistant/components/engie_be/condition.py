"""Purpose-specific automation conditions for the ENGIE Belgium integration."""

from collections.abc import Mapping
from typing import ClassVar, override

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    EntityNumericalConditionBase,
    EntityStateConditionBase,
)

from .const import DOMAIN


def _filter_by_translation_key(
    hass: HomeAssistant, entities: set[str], translation_key: str
) -> set[str]:
    """Return the ENGIE entities among entities that carry the translation key."""
    registry = er.async_get(hass)
    return {
        entity_id
        for entity_id in entities
        if (entry := registry.async_get(entity_id)) is not None
        and entry.platform == DOMAIN
        and entry.translation_key == translation_key
    }


class _EngieBinaryCondition(EntityStateConditionBase):
    """Base for binary sensor conditions tied to one ENGIE entity."""

    _domain_specs: Mapping[str, DomainSpec] = {BINARY_SENSOR_DOMAIN: DomainSpec()}
    _states = {STATE_ON}
    _translation_key: ClassVar[str]

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Restrict the targets to the ENGIE entity of this condition."""
        candidates = super().entity_filter(entities)
        return _filter_by_translation_key(self._hass, candidates, self._translation_key)


class _EngieSensorCondition(EntityNumericalConditionBase):
    """Base for numerical threshold conditions tied to one ENGIE sensor."""

    _domain_specs: Mapping[str, DomainSpec] = {SENSOR_DOMAIN: DomainSpec()}
    _translation_key: ClassVar[str]

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Restrict the targets to the ENGIE entity of this condition."""
        candidates = super().entity_filter(entities)
        return _filter_by_translation_key(self._hass, candidates, self._translation_key)


class EpexHourPriceIsNegativeCondition(_EngieBinaryCondition):
    """Condition that is true while the hourly EPEX price is negative."""

    _translation_key = "epex_negative"


class EpexQuarterHourPriceIsNegativeCondition(_EngieBinaryCondition):
    """Condition that is true while the quarter-hourly EPEX price is negative."""

    _translation_key = "epex_negative_quarter_hour"


class EpexHourPriceMeetsThresholdCondition(_EngieSensorCondition):
    """Condition that compares the current hourly EPEX price against a threshold."""

    _translation_key = "epex_current_hour"


class EpexQuarterHourPriceMeetsThresholdCondition(_EngieSensorCondition):
    """Condition that compares the current quarter-hourly EPEX price against a threshold."""

    _translation_key = "epex_current_quarter_hour"


CONDITIONS: dict[str, type[Condition]] = {
    "epex_hour_price_is_negative": EpexHourPriceIsNegativeCondition,
    "epex_hour_price_meets_threshold": EpexHourPriceMeetsThresholdCondition,
    "epex_quarter_hour_price_is_negative": EpexQuarterHourPriceIsNegativeCondition,
    "epex_quarter_hour_price_meets_threshold": (
        EpexQuarterHourPriceMeetsThresholdCondition
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the purpose-specific conditions for the ENGIE Belgium integration."""
    return CONDITIONS
