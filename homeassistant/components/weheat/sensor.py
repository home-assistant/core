"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass

from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WeheatConfigEntry
from .const import DISPLAY_PRECISION_COP, DISPLAY_PRECISION_WATTS
from .coordinator import WeheatDataUpdateCoordinator
from .entity import WeheatEntity


@dataclass(frozen=True, kw_only=True)
class WeHeatSensorEntityDescription(SensorEntityDescription):
    """Describes Weheat sensor entity."""

    value_fn: Callable[[HeatPump], StateType]


SENSORS = [
    WeHeatSensorEntityDescription(
        translation_key="power_output",
        key="power_output",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATTS,
        value_fn=lambda status: status.power_output,
    ),
    WeHeatSensorEntityDescription(
        translation_key="power_input",
        key="power_input",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATTS,
        value_fn=lambda status: status.power_input,
    ),
    WeHeatSensorEntityDescription(
        translation_key="cop",
        key="cop",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_COP,
        value_fn=lambda status: status.cop,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeheatConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors for weheat heat pump."""
    async_add_entities(
        WeheatHeatPumpSensor(coordinator, entity_description)
        for entity_description in SENSORS
        for coordinator in entry.runtime_data
    )


class WeheatHeatPumpSensor(WeheatEntity, SensorEntity):
    """Defines a Weheat heat pump sensor."""

    coordinator: WeheatDataUpdateCoordinator
    entity_description: WeHeatSensorEntityDescription

    def __init__(
        self,
        coordinator: WeheatDataUpdateCoordinator,
        entity_description: WeHeatSensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = f"{coordinator.heatpump_id}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
