"""Purpose-specific automation triggers for the ENGIE Belgium integration."""

from collections.abc import Mapping
from typing import ClassVar, override

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityNumericalStateCrossedThresholdTriggerBase,
    EntityTargetStateTriggerBase,
    EntityTriggerBase,
    Trigger,
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


class _EngieBinaryTrigger(EntityTargetStateTriggerBase):
    """Base for binary sensor edge triggers tied to one ENGIE entity."""

    _domain_specs: Mapping[str, DomainSpec] = {BINARY_SENSOR_DOMAIN: DomainSpec()}
    _translation_key: ClassVar[str]

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Restrict the targets to the ENGIE entity of this trigger."""
        candidates = super().entity_filter(entities)
        return _filter_by_translation_key(self._hass, candidates, self._translation_key)


class _EngieSensorTrigger(EntityTriggerBase):
    """Base for sensor value triggers tied to one ENGIE entity."""

    _domain_specs: Mapping[str, DomainSpec] = {SENSOR_DOMAIN: DomainSpec()}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA
    _translation_key: ClassVar[str]

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Restrict the targets to the ENGIE entity of this trigger."""
        candidates = super().entity_filter(entities)
        return _filter_by_translation_key(self._hass, candidates, self._translation_key)


class _EngieThresholdTrigger(EntityNumericalStateCrossedThresholdTriggerBase):
    """Base for threshold triggers tied to one ENGIE sensor."""

    _domain_specs: Mapping[str, DomainSpec] = {SENSOR_DOMAIN: DomainSpec()}
    _translation_key: ClassVar[str]

    @override
    def entity_filter(self, entities: set[str]) -> set[str]:
        """Restrict the targets to the ENGIE entity of this trigger."""
        candidates = super().entity_filter(entities)
        return _filter_by_translation_key(self._hass, candidates, self._translation_key)


class EpexHourBecameNegativeTrigger(_EngieBinaryTrigger):
    """Trigger that fires when the hourly EPEX price becomes negative."""

    _translation_key = "epex_negative"
    _to_states = {STATE_ON}


class EpexHourNoLongerNegativeTrigger(_EngieBinaryTrigger):
    """Trigger that fires when the hourly EPEX price is no longer negative."""

    _translation_key = "epex_negative"
    _to_states = {STATE_OFF}


class EpexQuarterHourBecameNegativeTrigger(_EngieBinaryTrigger):
    """Trigger that fires when the quarter-hourly EPEX price becomes negative."""

    _translation_key = "epex_negative_quarter_hour"
    _to_states = {STATE_ON}


class EpexQuarterHourNoLongerNegativeTrigger(_EngieBinaryTrigger):
    """Trigger that fires when the quarter-hourly EPEX price is no longer negative."""

    _translation_key = "epex_negative_quarter_hour"
    _to_states = {STATE_OFF}


class EpexTomorrowPricesPublishedTrigger(_EngieBinaryTrigger):
    """Trigger that fires when tomorrow's EPEX prices become available."""

    _translation_key = "epex_tomorrow_available"
    _to_states = {STATE_ON}
    _primary_entities_only = False


class EpexHighTodayHourUpdatedTrigger(_EngieSensorTrigger):
    """Trigger that fires when the highest hourly EPEX price of today changes."""

    _translation_key = "epex_high_today_hour"


class EpexLowTodayHourUpdatedTrigger(_EngieSensorTrigger):
    """Trigger that fires when the lowest hourly EPEX price of today changes."""

    _translation_key = "epex_low_today_hour"


class EpexHighTodayQuarterHourUpdatedTrigger(_EngieSensorTrigger):
    """Trigger that fires when the highest quarter-hourly EPEX price of today changes."""

    _translation_key = "epex_high_today_quarter_hour"


class EpexLowTodayQuarterHourUpdatedTrigger(_EngieSensorTrigger):
    """Trigger that fires when the lowest quarter-hourly EPEX price of today changes."""

    _translation_key = "epex_low_today_quarter_hour"


class EpexCurrentHourCrossedThresholdTrigger(_EngieThresholdTrigger):
    """Trigger that fires when the current hourly EPEX price crosses a threshold."""

    _translation_key = "epex_current_hour"


class EpexNextHourCrossedThresholdTrigger(_EngieThresholdTrigger):
    """Trigger that fires when the next hourly EPEX price crosses a threshold."""

    _translation_key = "epex_next_hour"


class EpexCurrentQuarterHourCrossedThresholdTrigger(_EngieThresholdTrigger):
    """Trigger that fires when the current quarter-hourly EPEX price crosses a threshold."""

    _translation_key = "epex_current_quarter_hour"


class EpexNextQuarterHourCrossedThresholdTrigger(_EngieThresholdTrigger):
    """Trigger that fires when the next quarter-hourly EPEX price crosses a threshold."""

    _translation_key = "epex_next_quarter_hour"


TRIGGERS: dict[str, type[Trigger]] = {
    "epex_current_hour_crossed_threshold": EpexCurrentHourCrossedThresholdTrigger,
    "epex_current_quarter_hour_crossed_threshold": (
        EpexCurrentQuarterHourCrossedThresholdTrigger
    ),
    "epex_high_today_hour_updated": EpexHighTodayHourUpdatedTrigger,
    "epex_high_today_quarter_hour_updated": EpexHighTodayQuarterHourUpdatedTrigger,
    "epex_hour_became_negative": EpexHourBecameNegativeTrigger,
    "epex_hour_no_longer_negative": EpexHourNoLongerNegativeTrigger,
    "epex_low_today_hour_updated": EpexLowTodayHourUpdatedTrigger,
    "epex_low_today_quarter_hour_updated": EpexLowTodayQuarterHourUpdatedTrigger,
    "epex_next_hour_crossed_threshold": EpexNextHourCrossedThresholdTrigger,
    "epex_next_quarter_hour_crossed_threshold": (
        EpexNextQuarterHourCrossedThresholdTrigger
    ),
    "epex_quarter_hour_became_negative": EpexQuarterHourBecameNegativeTrigger,
    "epex_quarter_hour_no_longer_negative": EpexQuarterHourNoLongerNegativeTrigger,
    "epex_tomorrow_prices_published": EpexTomorrowPricesPublishedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the purpose-specific triggers for the ENGIE Belgium integration."""
    return TRIGGERS
