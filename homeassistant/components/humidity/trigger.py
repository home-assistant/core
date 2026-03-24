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
from homeassistant.helpers.automation import NumericalDomainSpec
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
)

HUMIDITY_DOMAIN_SPECS: dict[str, NumericalDomainSpec] = {
    CLIMATE_DOMAIN: NumericalDomainSpec(
        value_source=CLIMATE_ATTR_CURRENT_HUMIDITY,
    ),
    HUMIDIFIER_DOMAIN: NumericalDomainSpec(
        value_source=HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
    ),
    SENSOR_DOMAIN: NumericalDomainSpec(
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    WEATHER_DOMAIN: NumericalDomainSpec(
        value_source=ATTR_WEATHER_HUMIDITY,
    ),
}

TRIGGERS: dict[str, type[Trigger]] = {
    "changed": make_entity_numerical_state_changed_trigger(
        HUMIDITY_DOMAIN_SPECS, valid_unit="%"
    ),
    "crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        HUMIDITY_DOMAIN_SPECS, valid_unit="%"
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for humidity."""
    return TRIGGERS
