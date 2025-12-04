"""Support for Helios ventilation unit binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HeliosDataUpdateCoordinator
from .entity import HeliosEntity


class HeliosBinarySensorEntity(HeliosEntity, BinarySensorEntity):
    """Representation of a Helios binary sensor."""

    entity_description: HeliosBinarySensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        name: str,
        coordinator: HeliosDataUpdateCoordinator,
        description: HeliosBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Helios binary sensor."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.get(self.entity_description.metric_key) == 1


@dataclass(frozen=True, kw_only=True)
class HeliosBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Helios binary sensor entity."""

    metric_key: str


BINARY_SENSOR_ENTITIES: tuple[HeliosBinarySensorEntityDescription, ...] = (
    HeliosBinarySensorEntityDescription(
        key="post_heater",
        translation_key="post_heater",
        metric_key="A_CYC_IO_HEATER",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""

    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        HeliosBinarySensorEntity(data["name"], data["coordinator"], description)
        for description in BINARY_SENSOR_ENTITIES
    )
