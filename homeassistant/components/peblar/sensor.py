"""Support for Peblar sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from peblar import PeblarMeter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PeblarConfigEntry, PeblarMeterDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class PeblarSensorDescription(SensorEntityDescription):
    """Describe an Peblar sensor."""

    value_fn: Callable[[PeblarMeter], int | None]


DESCRIPTIONS: tuple[PeblarSensorDescription, ...] = (
    PeblarSensorDescription(
        key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda x: x.energy_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Peblar sensors based on a config entry."""
    async_add_entities(
        PeblarSensorEntity(entry, description) for description in DESCRIPTIONS
    )


class PeblarSensorEntity(
    CoordinatorEntity[PeblarMeterDataUpdateCoordinator], SensorEntity
):
    """Defines a Peblar sensor."""

    entity_description: PeblarSensorDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PeblarConfigEntry,
        description: PeblarSensorDescription,
    ) -> None:
        """Initialize the Peblar entity."""
        super().__init__(entry.runtime_data.meter_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
