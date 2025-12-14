"""Binary sensor platform for Airobot thermostat."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyairobotrest.models import ThermostatStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirobotConfigEntry
from .entity import AirobotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirobotBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Airobot binary sensor entity."""

    value_fn: Callable[[ThermostatStatus], bool]


BINARY_SENSOR_TYPES: tuple[AirobotBinarySensorEntityDescription, ...] = (
    AirobotBinarySensorEntityDescription(
        key="window_open_detected",
        translation_key="window_open_detected",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda status: status.status_flags.window_open_detected,
        entity_registry_enabled_default=False,
    ),
    AirobotBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda status: status.status_flags.heating_on,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirobotBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    )


class AirobotBinarySensor(AirobotEntity, BinarySensorEntity):
    """Representation of an Airobot binary sensor."""

    entity_description: AirobotBinarySensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: AirobotBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.status.device_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data.status)
