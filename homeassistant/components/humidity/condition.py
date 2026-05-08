"""Provides conditions for humidity."""

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY as CLIMATE_ATTR_CURRENT_HUMIDITY,
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY as HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, EntityNumericalConditionBase

HUMIDITY_DOMAIN_SPECS = {
    CLIMATE_DOMAIN: DomainSpec(
        value_source=CLIMATE_ATTR_CURRENT_HUMIDITY,
    ),
    HUMIDIFIER_DOMAIN: DomainSpec(
        value_source=HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
    ),
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.HUMIDITY),
    WEATHER_DOMAIN: DomainSpec(
        value_source=ATTR_WEATHER_HUMIDITY,
    ),
}


class HumidityCondition(EntityNumericalConditionBase):
    """Condition for humidity value across multiple domains."""

    _domain_specs = HUMIDITY_DOMAIN_SPECS
    _valid_unit = PERCENTAGE

    def _should_include(self, state: State) -> bool:
        """Skip attribute-source entities that lack the humidity attribute.

        Mirrors the humidity trigger: for climate / humidifier / weather
        (attribute-based), the entity is filtered when the source attribute
        is absent; sensor entities (state-value-based) fall through to the
        base impl.
        """
        if not super()._should_include(state):
            return False
        domain_spec = self._domain_specs[state.domain]
        if domain_spec.value_source is None:
            return True
        return state.attributes.get(domain_spec.value_source) is not None


CONDITIONS: dict[str, type[Condition]] = {
    "is_value": HumidityCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for humidity."""
    return CONDITIONS
