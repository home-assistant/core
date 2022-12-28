"""Sensor platform for JvcProjector integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN as JVC_DOMAIN
from .entity import JvcProjectorEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from jvcprojector import JvcProjector

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .coordinator import JvcProjectorDataUpdateCoordinator


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required descriptor keys."""

    value_fn: Callable[[JvcProjector], StateType]


@dataclass
class JvcProjectorSensorEntityDescription(
    SensorEntityDescription, BaseEntityDescriptionMixin
):
    """Describes JvcProjector sensor entity."""


SENSOR_TYPES: tuple[JvcProjectorSensorEntityDescription, ...] = (
    JvcProjectorSensorEntityDescription(
        key="power",
        name="Power",
        icon="mdi:power",
        value_fn=lambda data: data["power"],
    ),
    JvcProjectorSensorEntityDescription(
        key="input",
        name="Input",
        icon="mdi:hdmi-port",
        value_fn=lambda data: data["input"],
    ),
    JvcProjectorSensorEntityDescription(
        key="signal",
        name="Signal",
        icon="mdi:signal",
        value_fn=lambda data: data["source"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform from a config entry."""
    coordinator = hass.data[JVC_DOMAIN][entry.entry_id]
    async_add_entities(
        JvcProjectorSensor(coordinator, description) for description in SENSOR_TYPES
    )


class JvcProjectorSensor(JvcProjectorEntity, SensorEntity):
    """Representation of a JvcProjector sensor."""

    entity_description: JvcProjectorSensorEntityDescription

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        entity_description: JvcProjectorSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._attr_unique_id}-{entity_description.key}"
        self._attr_name = f"{self._attr_name} {entity_description.name}"

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
