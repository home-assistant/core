"""Provides conditions for humidity."""

from __future__ import annotations

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY as CLIMATE_ATTR_CURRENT_HUMIDITY,
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY as HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec, NumericalDomainSpec
from homeassistant.helpers.condition import Condition, make_entity_numerical_condition

HUMIDITY_DOMAIN_SPECS = {
    CLIMATE_DOMAIN: NumericalDomainSpec(
        value_source=CLIMATE_ATTR_CURRENT_HUMIDITY,
    ),
    HUMIDIFIER_DOMAIN: NumericalDomainSpec(
        value_source=HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
    ),
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.HUMIDITY),
    NUMBER_DOMAIN: DomainSpec(device_class=NumberDeviceClass.HUMIDITY),
}

CONDITIONS: dict[str, type[Condition]] = {
    "value": make_entity_numerical_condition(HUMIDITY_DOMAIN_SPECS, PERCENTAGE),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for humidity."""
    return CONDITIONS
