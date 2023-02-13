"""SFR Box sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from sfrbox_api.models import DslInfo, SystemInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SFRDataUpdateCoordinator
from .models import DomainData

_T = TypeVar("_T")


@dataclass
class SFRBoxBinarySensorMixin(Generic[_T]):
    """Mixin for SFR Box sensors."""

    value_fn: Callable[[_T], bool | None]


@dataclass
class SFRBoxBinarySensorEntityDescription(
    BinarySensorEntityDescription, SFRBoxBinarySensorMixin[_T]
):
    """Description for SFR Box binary sensors."""


DSL_SENSOR_TYPES: tuple[SFRBoxBinarySensorEntityDescription[DslInfo], ...] = (
    SFRBoxBinarySensorEntityDescription[DslInfo](
        key="status",
        name="Status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.status == "up",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SFRBoxBinarySensor(data.dsl, description, data.system.data)
        for description in DSL_SENSOR_TYPES
    ]

    async_add_entities(entities)


class SFRBoxBinarySensor(
    CoordinatorEntity[SFRDataUpdateCoordinator[_T]], BinarySensorEntity
):
    """SFR Box sensor."""

    entity_description: SFRBoxBinarySensorEntityDescription[_T]
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SFRDataUpdateCoordinator[_T],
        description: SFRBoxBinarySensorEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{system_info.mac_addr}_{coordinator.name}_{description.key}"
        )
        self._attr_device_info = {"identifiers": {(DOMAIN, system_info.mac_addr)}}

    @property
    def is_on(self) -> bool | None:
        """Return the native value of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
