"""Sensor platform for the Hase iQ integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyhaseiq import Phase, Status

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HaseIQConfigEntry, HaseIQCoordinator


@dataclass(frozen=True, kw_only=True)
class HaseIQSensorEntityDescription(SensorEntityDescription):
    """Describes a Hase iQ sensor."""

    value_fn: Callable[[Status], StateType]


# The stove only reports the temperature and the heat-up while heating up, and the
# performance at nominal temperature: in any other phase, pyhaseiq returns None.
SENSORS: tuple[HaseIQSensorEntityDescription, ...] = (
    HaseIQSensorEntityDescription(
        key="phase",
        translation_key="phase",
        device_class=SensorDeviceClass.ENUM,
        options=[phase.name.lower() for phase in Phase],
        value_fn=lambda status: status.phase.name.lower(),
    ),
    HaseIQSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temperature,
    ),
    HaseIQSensorEntityDescription(
        key="heat_up",
        translation_key="heat_up",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.heat_up_percent,
    ),
    HaseIQSensorEntityDescription(
        key="performance",
        translation_key="performance",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.performance,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaseIQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hase iQ sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        HaseIQSensor(coordinator, description) for description in SENSORS
    )


class HaseIQSensor(CoordinatorEntity[HaseIQCoordinator], SensorEntity):
    """A reading of the stove."""

    _attr_has_entity_name = True
    entity_description: HaseIQSensorEntityDescription

    def __init__(
        self,
        coordinator: HaseIQCoordinator,
        description: HaseIQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # The stove exposes no serial number or MAC address, so the entry id stands in.
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.config_entry.title,
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the reading, or None outside the phase that reports it."""
        return self.entity_description.value_fn(self.coordinator.data)
