"""Support for Traccar server binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pytraccar import DeviceModel

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TraccarServerCoordinator
from .entity import TraccarServerEntity


@dataclass(frozen=True, kw_only=True)
class TraccarServerBinarySensorEntityDescription[_T](BinarySensorEntityDescription):
    """Describe Traccar Server sensor entity."""

    data_key: Literal["position", "device", "geofence", "attributes"]
    entity_registry_enabled_default = False
    entity_category = EntityCategory.DIAGNOSTIC
    value_fn: Callable[[_T], bool | None]


TRACCAR_SERVER_BINARY_SENSOR_ENTITY_DESCRIPTIONS: tuple[
    TraccarServerBinarySensorEntityDescription[Any], ...
] = (
    TraccarServerBinarySensorEntityDescription[DeviceModel](
        key="attributes.motion",
        data_key="position",
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda x: x["attributes"].get("motion", False),
    ),
    TraccarServerBinarySensorEntityDescription[DeviceModel](
        key="status",
        data_key="device",
        translation_key="status",
        value_fn=lambda x: None if (s := x["status"]) == "unknown" else s == "online",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: TraccarServerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TraccarServerBinarySensor(
            coordinator=coordinator,
            device=entry["device"],
            description=description,
        )
        for entry in coordinator.data.values()
        for description in TRACCAR_SERVER_BINARY_SENSOR_ENTITY_DESCRIPTIONS
    )


class TraccarServerBinarySensor[_T](TraccarServerEntity, BinarySensorEntity):
    """Represent a traccar server binary sensor."""

    _attr_has_entity_name = True
    entity_description: TraccarServerBinarySensorEntityDescription[_T]

    def __init__(
        self,
        coordinator: TraccarServerCoordinator,
        device: DeviceModel,
        description: TraccarServerBinarySensorEntityDescription[_T],
    ) -> None:
        """Initialize the Traccar Server sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = (
            f"{device['uniqueId']}_{description.data_key}_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the binary sensor is on or not."""
        return self.entity_description.value_fn(
            getattr(self, f"traccar_{self.entity_description.data_key}")
        )
