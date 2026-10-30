"""Support for IntelliClima Binary Sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyintelliclima import FanState, IntelliClimaECO2

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    IntelliClimaConfigEntry,
    IntelliClimaCoordinator,
    IntelliClimaFilterCoordinator,
)
from .entity import IntelliClimaECOEntity, eco_device_info

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IntelliClimaFanStateBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a binary sensor for one of the fan's running-state flags."""

    value_fn: Callable[[FanState], bool]


FAN_STATE_BINARY_SENSORS: tuple[
    IntelliClimaFanStateBinarySensorEntityDescription, ...
] = (
    IntelliClimaFanStateBinarySensorEntityDescription(
        key="boost",
        translation_key="boost",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda fan_state: fan_state.boost,
    ),
    IntelliClimaFanStateBinarySensorEntityDescription(
        key="night",
        translation_key="night",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda fan_state: fan_state.night,
    ),
    IntelliClimaFanStateBinarySensorEntityDescription(
        key="advanced",
        translation_key="advanced",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda fan_state: fan_state.advanced,
    ),
    IntelliClimaFanStateBinarySensorEntityDescription(
        key="profiled",
        translation_key="profiled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda fan_state: fan_state.profiled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the IntelliClima binary sensor platform."""
    data = entry.runtime_data
    ecocomfort2_devices = data.devices_coordinator.data.ecocomfort2_devices.values()

    entities: list[BinarySensorEntity] = [
        IntelliClimaFilterCleaningBinarySensor(
            coordinator=data.filter_coordinator, device=ecocomfort2
        )
        for ecocomfort2 in ecocomfort2_devices
    ]
    entities.extend(
        IntelliClimaFanStateBinarySensor(
            coordinator=data.devices_coordinator,
            device=ecocomfort2,
            description=description,
        )
        for ecocomfort2 in ecocomfort2_devices
        for description in FAN_STATE_BINARY_SENSORS
    )
    async_add_entities(entities)


class IntelliClimaFilterCleaningBinarySensor(
    CoordinatorEntity[IntelliClimaFilterCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether the device's filter needs cleaning."""

    _attr_has_entity_name = True
    _attr_translation_key = "filter_cleaning"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: IntelliClimaFilterCoordinator,
        device: IntelliClimaECO2,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator)

        self._attr_device_info = eco_device_info(device)
        self._device_sn = device.crono_sn
        self._attr_unique_id = f"{device.id}_filter_cleaning"

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        device_data = (self.coordinator.data or {}).get(self._device_sn)
        return super().available and device_data is not None and device_data.is_active

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the filter needs cleaning."""
        device_data = (self.coordinator.data or {}).get(self._device_sn)
        if device_data is None or not device_data.is_active:
            return None
        return device_data.change_filter


class IntelliClimaFanStateBinarySensor(IntelliClimaECOEntity, BinarySensorEntity):
    """Binary sensor for one of the fan's running-state flags."""

    entity_description: IntelliClimaFanStateBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO2,
        description: IntelliClimaFanStateBinarySensorEntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the flag is set."""
        if (fan_state := self._fan_state) is None:
            return None
        return self.entity_description.value_fn(fan_state)
