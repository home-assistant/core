"""Binary sensor platform for Weheat integration."""

from collections.abc import Callable
from dataclasses import dataclass

from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HeatPumpInfo, WeheatConfigEntry, WeheatDataUpdateCoordinator
from .entity import WeheatEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WeHeatBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Weheat binary sensor entity."""

    value_fn: Callable[[HeatPump], StateType]


BINARY_SENSORS = [
    WeHeatBinarySensorEntityDescription(
        translation_key="indoor_unit_water_pump_state",
        key="indoor_unit_water_pump_state",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda status: status.indoor_unit_water_pump_state,
    ),
    WeHeatBinarySensorEntityDescription(
        translation_key="indoor_unit_auxiliary_pump_state",
        key="indoor_unit_auxiliary_pump_state",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda status: status.indoor_unit_auxiliary_pump_state,
    ),
    WeHeatBinarySensorEntityDescription(
        translation_key="indoor_unit_dhw_valve_or_pump_state",
        key="indoor_unit_dhw_valve_or_pump_state",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda status: status.indoor_unit_dhw_valve_or_pump_state,
    ),
    WeHeatBinarySensorEntityDescription(
        translation_key="indoor_unit_gas_boiler_state",
        key="indoor_unit_gas_boiler_state",
        value_fn=lambda status: status.indoor_unit_gas_boiler_state,
    ),
    WeHeatBinarySensorEntityDescription(
        translation_key="indoor_unit_electric_heater_state",
        key="indoor_unit_electric_heater_state",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda status: status.indoor_unit_electric_heater_state,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WeheatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for weheat heat pump."""
    entities = [
        WeheatHeatPumpBinarySensor(
            weheatdata.heat_pump_info,
            weheatdata.data_coordinator,
            entity_description,
        )
        for weheatdata in entry.runtime_data
        for entity_description in BINARY_SENSORS
        if entity_description.value_fn(weheatdata.data_coordinator.data) is not None
    ]

    async_add_entities(entities)


class WeheatHeatPumpBinarySensor(WeheatEntity, BinarySensorEntity):
    """Defines a Weheat heat pump binary sensor."""

    heat_pump_info: HeatPumpInfo
    coordinator: WeheatDataUpdateCoordinator
    entity_description: WeHeatBinarySensorEntityDescription

    def __init__(
        self,
        heat_pump_info: HeatPumpInfo,
        coordinator: WeheatDataUpdateCoordinator,
        entity_description: WeHeatBinarySensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(heat_pump_info, coordinator)
        self.entity_description = entity_description

        self._attr_unique_id = f"{heat_pump_info.heatpump_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        value = self.entity_description.value_fn(self.coordinator.data)
        return bool(value) if value is not None else None
