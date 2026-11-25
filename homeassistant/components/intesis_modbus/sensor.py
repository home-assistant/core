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

from .coordinator import IntesisConfigEntry, IntesisCoordinator, IntesisUnitCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IntesisSensorEntityDescription(SensorEntityDescription):
    """A sensor, and where to read its value off the gateway."""

    report_name: str
    value_fn: Callable[[IntesisSingleUnitGateway], StateType]


def _error_code(device: IntesisSingleUnitGateway) -> str | None:
    """The code the remote controller shows for an error of the air conditioner.

    An error the library has no remote controller code for shows as the
    number the gateway reports.
    """
    if (error := device.error) is None or error.state is not ErrorState.UNIT_ERROR:
        return None
    return error.remote_code or str(error.code)


# What the gateway knows by itself: these stay available while it cannot reach
# the air conditioner, and the error sensor then says so.
GATEWAY_SENSORS: Final[tuple[IntesisSensorEntityDescription, ...]] = (
    IntesisSensorEntityDescription(
        key="error",
        translation_key="error",
        report_name="control",
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
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_error_code,
    ),
    IntesisSensorEntityDescription(
        key="undervoltage_hours",
        translation_key="undervoltage_hours",
        report_name="status",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.undervoltage_hours,
    ),
)

UNIT_SENSORS: Final[tuple[IntesisSensorEntityDescription, ...]] = (
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
        key="operation_hours",
        translation_key="operation_hours",
        report_name="control",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.operation_hours,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of the gateway and its air conditioner."""
    data = entry.runtime_data
    async_add_entities(
        [
            *(
                IntesisSensor(data.gateway, description)
                for description in GATEWAY_SENSORS
            ),
            *(IntesisSensor(data.unit, description) for description in UNIT_SENSORS),
        ]
    )


class IntesisSensor(IntesisEntity, SensorEntity):
    """A value of an Intesis gateway or of the air conditioner behind it."""

    entity_description: IntesisSensorEntityDescription

    def __init__(
        self,
        coordinator: IntesisCoordinator | IntesisUnitCoordinator,
        description: IntesisSensorEntityDescription,
    ) -> None:
        """Bind to the device the description reads, through its coordinator."""
        super().__init__(coordinator, description.key, description.report_name)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """The value the gateway reported in the most recent poll."""
        return self.entity_description.value_fn(self.coordinator.device)
