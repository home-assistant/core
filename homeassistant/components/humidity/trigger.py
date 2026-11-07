"""Provides triggers for humidity."""

from typing import override

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityStateAttribute,
)
from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    HumidifierEntityStateAttribute,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    WeatherEntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerBase,
    EntityNumericalStateCrossedThresholdTriggerBase,
    EntityNumericalStateTriggerBase,
    Trigger,
)

HUMIDITY_DOMAIN_SPECS: dict[str, DomainSpec] = {
    CLIMATE_DOMAIN: DomainSpec(
        value_source=ClimateEntityStateAttribute.CURRENT_HUMIDITY,
    ),
    HUMIDIFIER_DOMAIN: DomainSpec(
        value_source=HumidifierEntityStateAttribute.CURRENT_HUMIDITY,
    ),
    SENSOR_DOMAIN: DomainSpec(
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WEATHER_DOMAIN: DomainSpec(
        value_source=WeatherEntityStateAttribute.HUMIDITY,
    ),
}


class _HumidityTriggerMixin(EntityNumericalStateTriggerBase):
    """Mixin for humidity triggers providing entity filtering."""

    _domain_specs = HUMIDITY_DOMAIN_SPECS
    _valid_unit = "%"

    @override
    def _should_include(self, state: State) -> bool:
        """Skip attribute-source entities that lack the humidity attribute.

        For domains whose tracked value comes from an attribute
        (climate / humidifier / weather), require the attribute to be
        present; otherwise the all/count check would treat an entity that
        cannot report a humidity as a non-match and block behavior=last.
        Sensor entities source their value from `state.state`, so they
        fall through to the base impl.
        """
        if not super()._should_include(state):
            return False
        domain_spec = self._domain_specs[state.domain]
        if domain_spec.value_source is None:
            return True
        return state.attributes.get(domain_spec.value_source) is not None


class HumidityChangedTrigger(
    _HumidityTriggerMixin, EntityNumericalStateChangedTriggerBase
):
    """Trigger for humidity value changes across multiple domains."""


class HumidityCrossedThresholdTrigger(
    _HumidityTriggerMixin, EntityNumericalStateCrossedThresholdTriggerBase
):
    """Trigger for humidity value crossing a threshold across multiple domains."""


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": HumidityChangedTrigger,
    "crossed_threshold": HumidityCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for humidity."""
    return TRIGGERS
