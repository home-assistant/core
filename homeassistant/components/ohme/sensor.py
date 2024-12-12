"""Platform for sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from ohme import ChargerStatus, OhmeApiClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import OhmeEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OhmeSensorDescription(SensorEntityDescription):
    """Class describing Ohme sensor entities."""

    value_fn: Callable[[OhmeApiClient], Any]
    is_supported_fn: Callable[[OhmeApiClient], bool] = lambda _: True


SENSOR_DESCRIPTIONS = [
    OhmeSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in ChargerStatus],
        value_fn=lambda client: client.status.value,
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
        if description.is_supported_fn(client)
    ]

    async_add_entities(sensors)


class OhmeSensor(OhmeEntity, SensorEntity):
    """Generic sensor for Ohme."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
