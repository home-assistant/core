"""Support for LetPot sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from letpot.models import (
    DeviceFeature,
    LetPotDeviceStatus,
    LetPotGardenStatus,
    TemperatureUnit,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator
from .entity import LetPotEntity, LetPotEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


LETPOT_TEMPERATURE_UNIT_HA_UNIT = {
    TemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
    TemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}


@dataclass(frozen=True, kw_only=True)
class LetPotSensorEntityDescription[_DataT: LetPotDeviceStatus](
    LetPotEntityDescription, SensorEntityDescription
):
    """Describes a LetPot sensor entity."""

    native_unit_of_measurement_fn: Callable[[_DataT], str | None]
    value_fn: Callable[[_DataT], StateType]


SENSORS: tuple[LetPotSensorEntityDescription[LetPotGardenStatus], ...] = (
    LetPotSensorEntityDescription[LetPotGardenStatus](
        key="temperature",
        value_fn=lambda status: status.temperature_value,
        native_unit_of_measurement_fn=(
            lambda status: LETPOT_TEMPERATURE_UNIT_HA_UNIT[
                status.temperature_unit or TemperatureUnit.CELSIUS
            ]
        ),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=(
            lambda coordinator: (
                DeviceFeature.TEMPERATURE
                in coordinator.device_client.device_info(
                    coordinator.device.serial_number
                ).features
            )
        ),
    ),
    LetPotSensorEntityDescription[LetPotGardenStatus](
        key="water_level",
        translation_key="water_level",
        value_fn=lambda status: status.water_level,
        native_unit_of_measurement_fn=lambda _: PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=(
            lambda coordinator: (
                DeviceFeature.WATER_LEVEL
                in coordinator.device_client.device_info(
                    coordinator.device.serial_number
                ).features
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetPotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LetPot sensor entities based on a device features."""
    coordinators = entry.runtime_data
    async_add_entities(
        LetPotSensorEntity[LetPotGardenStatus](coordinator, description)
        for description in SENSORS
        for coordinator in coordinators
        if description.supported_fn(coordinator)
    )


class LetPotSensorEntity[_DataT: LetPotDeviceStatus](
    LetPotEntity[_DataT], SensorEntity
):
    """Defines a LetPot sensor entity."""

    entity_description: LetPotSensorEntityDescription[_DataT]

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator[_DataT],
        description: LetPotSensorEntityDescription[_DataT],
    ) -> None:
        """Initialize LetPot sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}"
            f"_{coordinator.device.serial_number}"
            f"_{description.key}"
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        return self.entity_description.native_unit_of_measurement_fn(
            self.coordinator.data
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
