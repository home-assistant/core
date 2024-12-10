"""Platform for sensor."""

from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .coordinator import OhmeApiResponse, OhmeCoordinator
from .entity import OhmeEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OhmeSensorDescription(SensorEntityDescription):
    """Class describing Ohme sensor entities."""

    value_fn: Callable[[OhmeApiResponse], Any]

def charge_status(data: OhmeApiResponse):
    """Determine charge status from API responses."""

    if data.charge_sessions["mode"] == "PENDING_APPROVAL":
        return "pending_approval"
    if data.charge_sessions["mode"] == "DISCONNECTED":
        return "unplugged"
    elif data.charge_sessions.get("power") and data.charge_sessions["power"].get("watt", 0) > 0:
        return "charging"
    else:
        return "plugged_in"

SENSOR_DESCRIPTIONS = [
    OhmeSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["unplugged", "pending_approval", "plugged_in", "charging"],
        value_fn=charge_status
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors and configure coordinator."""
    coordinator = config_entry.runtime_data
    client = coordinator.client

    sensors = [
        OhmeSensor(coordinator, client, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(sensors)


class OhmeSensor(OhmeEntity, SensorEntity):
    """Generic sensor for Ohme."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
