"""Provides triggers for occupancy."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    EntityTargetStateTriggerBase,
    EntityTriggerBase,
    Trigger,
)


class _OccupancyBinaryTriggerBase(EntityTriggerBase):
    """Base trigger for occupancy binary sensor state changes."""

    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.OCCUPANCY)
    }


class OccupancyDetectedTrigger(
    _OccupancyBinaryTriggerBase, EntityTargetStateTriggerBase
):
    """Trigger for occupancy detected (binary sensor ON)."""

    _to_states = {STATE_ON}


class OccupancyClearedTrigger(
    _OccupancyBinaryTriggerBase, EntityTargetStateTriggerBase
):
    """Trigger for occupancy cleared (binary sensor OFF)."""

    _to_states = {STATE_OFF}


TRIGGERS: dict[str, type[Trigger]] = {
    "detected": OccupancyDetectedTrigger,
    "cleared": OccupancyClearedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for occupancy."""
    return TRIGGERS
