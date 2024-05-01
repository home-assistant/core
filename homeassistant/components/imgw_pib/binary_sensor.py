"""IMGW-PIB binary sensor platform."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from imgw_pib.model import HydrologicalData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImgwPibConfigEntry
from .const import ATTRIBUTION
from .coordinator import ImgwPibDataUpdateCoordinator

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ImgwPibBinarySensorEntityDescription(BinarySensorEntityDescription):
    """IMGW-PIB sensor entity description."""

    value: Callable[[HydrologicalData], bool | None]
    attrs: Callable[[HydrologicalData], dict[str, Any]]


BINARY_SENSOR_TYPES: tuple[ImgwPibBinarySensorEntityDescription, ...] = (
    ImgwPibBinarySensorEntityDescription(
        key="flood_warning",
        translation_key="flood_warning",
        device_class=BinarySensorDeviceClass.SAFETY,
        value=lambda data: data.flood_warning,
        attrs=lambda data: {"warning_level": data.flood_warning_level.value},
    ),
    ImgwPibBinarySensorEntityDescription(
        key="flood_alarm",
        translation_key="flood_alarm",
        device_class=BinarySensorDeviceClass.SAFETY,
        value=lambda data: data.flood_alarm,
        attrs=lambda data: {"alarm_level": data.flood_alarm_level.value},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImgwPibConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a IMGW-PIB binary sensor entity from a config_entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        ImgwPibBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSOR_TYPES
        if getattr(coordinator.data, description.key) is not None
    )


class ImgwPibBinarySensorEntity(
    CoordinatorEntity[ImgwPibDataUpdateCoordinator], BinarySensorEntity
):
    """Define IMGW-PIB binary sensor entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: ImgwPibBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ImgwPibDataUpdateCoordinator,
        description: ImgwPibBinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.station_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        return self.entity_description.attrs(self.coordinator.data)
