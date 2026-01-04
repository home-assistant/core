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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry, get_panel_field, unique_base
from .hub import Elke27Hub


@dataclass(frozen=True, slots=True, kw_only=True)
class Elke27SensorDescription(SensorEntityDescription):
    """Describe an Elke27 sensor."""

    key: str
    value_fn: Callable[[Elke27Hub], Any]


SENSORS: tuple[Elke27SensorDescription, ...] = (
    Elke27SensorDescription(
        key="panel_name",
        translation_key="panel_name",
        value_fn=lambda hub: get_panel_field(hub, "name"),
    ),
    Elke27SensorDescription(
        key="panel_ready",
        translation_key="panel_ready",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda hub: "ready" if hub.is_ready else "not_ready",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 sensors from a config entry."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Elke27Sensor(hub, entry, description) for description in SENSORS
    )


class Elke27Sensor(SensorEntity):
    """Representation of an Elke27 sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self, hub: Elke27Hub, entry: ConfigEntry, description: Elke27SensorDescription
    ) -> None:
        """Initialize the sensor."""
        self._hub = hub
        self._entry = entry
        self.entity_description = description
        self._attr_device_class = description.device_class
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{unique_base(hub, entry)}_{description.key}"
        self._attr_device_info = device_info_for_entry(hub, entry)

    async def async_added_to_hass(self) -> None:
        """Register for hub updates."""
        self.async_on_remove(self._hub.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write updated state."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self._hub)
