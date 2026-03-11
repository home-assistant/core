"""Provides triggers for humidity."""

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
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers.trigger import (
    EntityNumericalStateAttributeChangedTriggerBase,
    EntityNumericalStateAttributeCrossedThresholdTriggerBase,
    EntityTriggerBase,
    Trigger,
    get_device_class_or_undefined,
)


class _HumidityTriggerMixin(EntityTriggerBase):
    """Mixin for humidity triggers providing entity filtering and value extraction."""

    _attributes = {
        CLIMATE_DOMAIN: CLIMATE_ATTR_CURRENT_HUMIDITY,
        HUMIDIFIER_DOMAIN: HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
        SENSOR_DOMAIN: None,  # Use state.state
        WEATHER_DOMAIN: ATTR_WEATHER_HUMIDITY,
    }
    _domains = {SENSOR_DOMAIN, CLIMATE_DOMAIN, HUMIDIFIER_DOMAIN, WEATHER_DOMAIN}

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities: all climate/humidifier/weather, sensor only with device_class humidity."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if split_entity_id(entity_id)[0] != SENSOR_DOMAIN
            or get_device_class_or_undefined(self._hass, entity_id)
            == SensorDeviceClass.HUMIDITY
        }


class HumidityChangedTrigger(
    _HumidityTriggerMixin, EntityNumericalStateAttributeChangedTriggerBase
):
    """Trigger for humidity value changes across multiple domains."""


class HumidityCrossedThresholdTrigger(
    _HumidityTriggerMixin, EntityNumericalStateAttributeCrossedThresholdTriggerBase
):
    """Trigger for humidity value crossing a threshold across multiple domains."""


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": HumidityChangedTrigger,
    "crossed_threshold": HumidityCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for humidity."""
    return TRIGGERS
