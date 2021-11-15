"""Support for Vallox ventilation unit binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ValloxDataUpdateCoordinator
from .const import DOMAIN


class ValloxBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Vallox binary sensor."""

    entity_description: ValloxBinarySensorEntityDescription
    coordinator: ValloxDataUpdateCoordinator

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Vallox binary sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_name = f"{name} {description.name}"

        uuid = self.coordinator.data.get_uuid()
        self._attr_unique_id = f"{uuid}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (metric_key := self.entity_description.metric_key) is None:
            return None
        return self.coordinator.data.get_metric(metric_key) == 1


@dataclass
class ValloxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Vallox binary sensor entity."""

    metric_key: str | None = None
    sensor_type: type[ValloxBinarySensor] = ValloxBinarySensor


SENSORS: tuple[ValloxBinarySensorEntityDescription, ...] = (
    ValloxBinarySensorEntityDescription(
        key="post_heater",
        name="Post Heater",
        icon="mdi:radiator",
        metric_key="A_CYC_IO_HEATER",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""

    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            description.sensor_type(data["name"], data["coordinator"], description)
            for description in SENSORS
        ]
    )
