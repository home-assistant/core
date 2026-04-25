"""Support for OpenEVSE number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from openevsehttp.__main__ import OpenEVSE

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_SERIAL_NUMBER,
    EntityCategory,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSENumberDescription(NumberEntityDescription):
    """Describes an OpenEVSE number entity."""

    value_fn: Callable[[OpenEVSE], float]
    min_value_fn: Callable[[OpenEVSE], float]
    max_value_fn: Callable[[OpenEVSE], float]
    set_value_fn: Callable[[OpenEVSE, float], Awaitable[Any]]


NUMBER_TYPES: tuple[OpenEVSENumberDescription, ...] = (
    OpenEVSENumberDescription(
        key="charge_rate",
        translation_key="charge_rate",
        value_fn=lambda ev: ev.max_current_soft,
        min_value_fn=lambda ev: ev.min_amps,
        max_value_fn=lambda ev: ev.max_amps,
        set_value_fn=lambda ev, value: ev.set_current(value),
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE sensors based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSENumber(coordinator, description, identifier, entry.unique_id)
        for description in NUMBER_TYPES
    )


class OpenEVSENumber(CoordinatorEntity[OpenEVSEDataUpdateCoordinator], NumberEntity):
    """Implementation of an OpenEVSE sensor."""

    _attr_has_entity_name = True
    entity_description: OpenEVSENumberDescription

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: OpenEVSENumberDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, unique_id)
            }
            self._attr_device_info[ATTR_SERIAL_NUMBER] = unique_id

    @property
    def native_value(self) -> float:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.coordinator.charger)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.entity_description.min_value_fn(self.coordinator.charger)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.entity_description.max_value_fn(self.coordinator.charger)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.set_value_fn(self.coordinator.charger, value)
