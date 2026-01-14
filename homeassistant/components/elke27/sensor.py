"""Sensors for the Elke27 integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_HUB, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .entity import (
    build_unique_id,
    device_info_for_entry,
    get_panel_field,
    unique_base,
)
from .hub import Elke27Hub


@dataclass(frozen=True, slots=True, kw_only=True)
class Elke27SensorDescription(SensorEntityDescription):
    """Describe an Elke27 sensor."""

    key: str
    numeric_id: int
    value_fn: Callable[[Elke27Hub, Any | None], Any]


SENSORS: tuple[Elke27SensorDescription, ...] = (
    Elke27SensorDescription(
        key="panel_name",
        numeric_id=1,
        translation_key="panel_name",
        value_fn=lambda hub, snapshot: get_panel_field(snapshot, hub.panel_name, "name"),
    ),
    Elke27SensorDescription(
        key="panel_ready",
        numeric_id=2,
        translation_key="panel_ready",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda hub, snapshot: (
            "connected" if hub.is_ready else "disconnected"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: Elke27Hub = data[DATA_HUB]
    coordinator: Elke27DataUpdateCoordinator = data[DATA_COORDINATOR]
    async_add_entities(
        Elke27Sensor(coordinator, hub, entry, description) for description in SENSORS
    )


class Elke27Sensor(CoordinatorEntity[Elke27DataUpdateCoordinator], SensorEntity):
    """Representation of an Elke27 sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        description: Elke27SensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self.entity_description = description
        self._attr_device_class = description.device_class
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "panel",
            description.numeric_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self._hub, self.coordinator.data)
