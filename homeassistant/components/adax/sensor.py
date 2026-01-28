"""Support for Adax energy sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AdaxConfigEntry
from .const import CONNECTION_TYPE, DOMAIN, LOCAL
from .coordinator import AdaxCloudCoordinator


@dataclass(kw_only=True, frozen=True)
class AdaxSensorDescription(SensorEntityDescription):
    """Describes Adax sensor entity."""

    data_key: str


SENSORS: tuple[AdaxSensorDescription, ...] = (
    AdaxSensorDescription(
        key="temperature",
        data_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    AdaxSensorDescription(
        key="energy",
        data_key="energyWh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdaxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Adax sensors with config flow."""
    if entry.data.get(CONNECTION_TYPE) != LOCAL:
        cloud_coordinator = cast(AdaxCloudCoordinator, entry.runtime_data)

        # Create individual energy sensors for each device
        async_add_entities(
            [
                AdaxSensor(cloud_coordinator, entity_description, device_id)
                for device_id in cloud_coordinator.data
                for entity_description in SENSORS
            ]
        )


class AdaxSensor(CoordinatorEntity[AdaxCloudCoordinator], SensorEntity):
    """Representation of an Adax sensor."""

    entity_description: AdaxSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AdaxCloudCoordinator,
        entity_description: AdaxSensorDescription,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._device_id = device_id
        room = coordinator.data[device_id]

        self._attr_unique_id = (
            f"{room['homeId']}_{device_id}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=room["name"],
            manufacturer="Adax",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.data_key
            in self.coordinator.data[self._device_id]
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the native value of the sensor."""
        return self.coordinator.data[self._device_id].get(
            self.entity_description.data_key
        )
