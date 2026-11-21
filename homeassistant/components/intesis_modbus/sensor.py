"""Sensors for what an Intesis gateway reports about its air conditioner."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, override

from intesis_gw_modbus import ErrorState, IntesisSingleUnitGateway

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import IntesisConfigEntry, IntesisCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IntesisSensorEntityDescription(SensorEntityDescription):
    """A sensor, and where to read its value off the gateway."""

    report_name: str
    value_fn: Callable[[IntesisSingleUnitGateway], StateType]
    available_without_unit: bool = False


SENSORS: Final[tuple[IntesisSensorEntityDescription, ...]] = (
    IntesisSensorEntityDescription(
        key="outdoor_intake_temperature",
        translation_key="outdoor_intake_temperature",
        report_name="temperatures",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.outdoor_intake_temperature,
    ),
    IntesisSensorEntityDescription(
        key="return_path_temperature",
        translation_key="return_path_temperature",
        report_name="temperatures",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.return_path_temperature,
    ),
    IntesisSensorEntityDescription(
        key="error",
        translation_key="error",
        report_name="control",
        available_without_unit=True,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[state.value for state in ErrorState],
        value_fn=lambda device: (
            None if (error := device.error) is None else error.state.value
        ),
    ),
    IntesisSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        report_name="control",
        available_without_unit=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            None if (error := device.error) is None else error.remote_code
        ),
    ),
    IntesisSensorEntityDescription(
        key="operation_hours",
        translation_key="operation_hours",
        report_name="control",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.operation_hours,
    ),
    IntesisSensorEntityDescription(
        key="undervoltage_hours",
        translation_key="undervoltage_hours",
        report_name="status",
        available_without_unit=True,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda device: device.undervoltage_hours,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of the gateway and its air conditioner."""
    async_add_entities(
        IntesisSensor(entry.runtime_data, description) for description in SENSORS
    )


class IntesisSensor(IntesisEntity, SensorEntity):
    """A value read off an Intesis gateway."""

    entity_description: IntesisSensorEntityDescription

    def __init__(
        self,
        coordinator: IntesisCoordinator,
        description: IntesisSensorEntityDescription,
    ) -> None:
        """Bind to the gateway the description reads."""
        super().__init__(
            coordinator,
            description.key,
            description.report_name,
            available_without_unit=description.available_without_unit,
        )
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """The value the gateway reported in the most recent poll."""
        return self.entity_description.value_fn(self.coordinator.device)
