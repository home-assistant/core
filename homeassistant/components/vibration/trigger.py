"""Provides triggers for vibration."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import Trigger, make_entity_target_state_trigger

VIBRATION_DOMAIN_SPECS: dict[str, DomainSpec] = {
    BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.VIBRATION),
}

TRIGGERS: dict[str, type[Trigger]] = {
    "detected": make_entity_target_state_trigger(VIBRATION_DOMAIN_SPECS, STATE_ON),
    "cleared": make_entity_target_state_trigger(VIBRATION_DOMAIN_SPECS, STATE_OFF),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for vibration."""
    return TRIGGERS
