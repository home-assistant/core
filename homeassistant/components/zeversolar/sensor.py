"""Support for the Zeversolar platform."""

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    ZeversolarConfigEntry,
    ZeversolarCoordinator,
    ZeversolarCoordinatorData,
)
from .entity import ZeversolarEntity


@dataclass(frozen=True, kw_only=True)
class ZeversolarEntityDescription(SensorEntityDescription):
    """Describes Zeversolar sensor entity."""

    value_fn: Callable[[ZeversolarCoordinatorData], int | float]
    available_fn: Callable[[ZeversolarCoordinator], bool] = field(
        default_factory=lambda: lambda _: True
    )


SENSOR_TYPES = (
    ZeversolarEntityDescription(
        key="pac",
        translation_key="pac",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data["inverter_data"].pac,
    ),
    ZeversolarEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data["inverter_data"].energy_today,
    ),
    ZeversolarEntityDescription(
        key="power_limit",
        translation_key="power_limit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["power_limit"],
        available_fn=lambda coordinator: coordinator.power_limit_supported,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeversolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zeversolar sensor."""
    coordinator = entry.runtime_data
    async_add_entities(
        ZeversolarSensor(
            description=description,
            coordinator=coordinator,
        )
        for description in SENSOR_TYPES
    )


class ZeversolarSensor(ZeversolarEntity, SensorEntity):
    """Implementation of the Zeversolar sensor."""

    entity_description: ZeversolarEntityDescription

    def __init__(
        self,
        *,
        description: ZeversolarEntityDescription,
        coordinator: ZeversolarCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = (
            f"{coordinator.data['inverter_data'].serial_number}_{description.key}"
        )

    @property
    def available(self) -> bool:
        """Return False if this sensor requires an unsupported API."""
        return super().available and self.entity_description.available_fn(
            self.coordinator
        )

    @property
    def native_value(self) -> int | float:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
