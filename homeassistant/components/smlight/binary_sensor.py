"""Support for SLZB-06 binary sensors."""

from __future__ import annotations

from _collections_abc import Callable
from dataclasses import dataclass

from pysmlight import Sensors

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmDataUpdateCoordinator
from .entity import SmEntity


@dataclass(frozen=True, kw_only=True)
class SmBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing SMLIGHT binary sensor entities."""

    value_fn: Callable[[Sensors], bool]


SENSORS = [
    SmBinarySensorEntityDescription(
        key="ethernet",
        translation_key="ethernet",
        value_fn=lambda x: x.ethernet,
    ),
    SmBinarySensorEntityDescription(
        key="wifi",
        translation_key="wifi",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.wifi_connected,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SmBinarySensorEntity(coordinator, description) for description in SENSORS
    )


class SmBinarySensorEntity(SmEntity, BinarySensorEntity):
    """Representation of a slzb binary sensor."""

    entity_description: SmBinarySensorEntityDescription
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmBinarySensorEntityDescription,
    ) -> None:
        """Initialize slzb binary sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.sensors)
