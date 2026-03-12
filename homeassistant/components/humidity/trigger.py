"""Provides triggers for humidity."""

from __future__ import annotations

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    EntityNumericalStateAttributeChangedTriggerBase,
    EntityNumericalStateAttributeCrossedThresholdTriggerBase,
    NumericalValueSource,
    Trigger,
)

HUMIDITY_MATCH_SPECS: dict[str, NumericalValueSource] = {
    CLIMATE_DOMAIN: NumericalValueSource(
        value_source=CLIMATE_ATTR_CURRENT_HUMIDITY,
    ),
    HUMIDIFIER_DOMAIN: NumericalValueSource(
        value_source=HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
    ),
    SENSOR_DOMAIN: NumericalValueSource(
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WEATHER_DOMAIN: NumericalValueSource(
        value_source=ATTR_WEATHER_HUMIDITY,
    ),
}


class HumidityChangedTrigger(EntityNumericalStateAttributeChangedTriggerBase):
    """Trigger for humidity value changes across multiple domains."""

    _value_sources = HUMIDITY_MATCH_SPECS


class HumidityCrossedThresholdTrigger(
    EntityNumericalStateAttributeCrossedThresholdTriggerBase
):
    """Trigger for humidity value crossing a threshold across multiple domains."""

    _value_sources = HUMIDITY_MATCH_SPECS


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": HumidityChangedTrigger,
    "crossed_threshold": HumidityCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for humidity."""
    return TRIGGERS
