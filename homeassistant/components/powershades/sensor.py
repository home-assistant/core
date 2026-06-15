"""PowerShades sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PowerShadesConfigEntry, PowerShadesCoordinator, PowerShadesData
from .entity import PowerShadesEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PowerShadesSensorDescription(SensorEntityDescription):
    """Describes a PowerShades sensor."""

    value_fn: Callable[[PowerShadesData], int | None]


SENSORS: tuple[PowerShadesSensorDescription, ...] = (
    PowerShadesSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery_percentage,
    ),
    PowerShadesSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery_mv,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerShadesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PowerShades sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        PowerShadesSensor(coordinator, description) for description in SENSORS
    )


class PowerShadesSensor(PowerShadesEntity, SensorEntity):
    """PowerShades diagnostic sensor."""

    entity_description: PowerShadesSensorDescription

    def __init__(
        self,
        coordinator: PowerShadesCoordinator,
        description: PowerShadesSensorDescription,
    ) -> None:
        """Initialize the PowerShades sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
