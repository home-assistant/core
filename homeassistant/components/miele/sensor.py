"""Sensor platform for Miele integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Final, cast

from pymiele import MieleDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import STATE_STATUS_TAGS, MieleAppliance, StateStatus
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleSensorDescription(SensorEntityDescription):
    """Class describing Miele sensor entities."""

    value_fn: Callable[[MieleDevice], StateType]
    zone: int | None = None


@dataclass
class MieleSensorDefinition:
    """Class for defining sensor entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleSensorDescription


SENSOR_TYPES: Final[tuple[MieleSensorDefinition, ...]] = (
    MieleSensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.HOB_HIGHLIGHT,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.HOB_INDUCTION,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.HOB_INDUCT_EXTR,
        ),
        description=MieleSensorDescription(
            key="state_status",
            translation_key="status",
            value_fn=lambda value: value.state_status,
            device_class=SensorDeviceClass.ENUM,
            options=list(STATE_STATUS_TAGS.values()),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSensorDescription(
            key="state_temperature_1",
            zone=1,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda value: cast(int, value.state_temperatures[0].temperature)
            / 100.0,
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN_COMBI,
        ),
        description=MieleSensorDescription(
            key="state_core_temperature",
            translation_key="core_temperature",
            zone=1,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=(
                lambda value: cast(int, value.state_core_temperature[0].temperature)
                / 100.0
            ),
        ),
    ),
    MieleSensorDefinition(
        types=(
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN_COMBI,
        ),
        description=MieleSensorDescription(
            key="state_core_target_temperature",
            translation_key="core_target_temperature",
            zone=1,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=(
                lambda value: cast(
                    int, value.state_core_target_temperature[0].temperature
                )
                / 100.0
            ),
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    entities: list = []
    entity_class: type[MieleSensor]
    for device_id, device in coordinator.data.devices.items():
        for definition in SENSOR_TYPES:
            if device.device_type in definition.types:
                match definition.description.key:
                    case "state_status":
                        entity_class = MieleStatusSensor
                    case _:
                        entity_class = MieleSensor
                entities.append(
                    entity_class(coordinator, device_id, definition.description)
                )

    async_add_entities(entities)


APPLIANCE_ICONS = {
    MieleAppliance.WASHING_MACHINE: "mdi:washing-machine",
    MieleAppliance.TUMBLE_DRYER: "mdi:tumble-dryer",
    MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL: "mdi:tumble-dryer",
    MieleAppliance.DISHWASHER: "mdi:dishwasher",
    MieleAppliance.OVEN: "mdi:chef-hat",
    MieleAppliance.OVEN_MICROWAVE: "mdi:chef-hat",
    MieleAppliance.HOB_HIGHLIGHT: "mdi:pot-steam-outline",
    MieleAppliance.STEAM_OVEN: "mdi:chef-hat",
    MieleAppliance.MICROWAVE: "mdi:microwave",
    MieleAppliance.COFFEE_SYSTEM: "mdi:coffee-maker",
    MieleAppliance.HOOD: "mdi:turbine",
    MieleAppliance.FRIDGE: "mdi:fridge-industrial-outline",
    MieleAppliance.FREEZER: "mdi:fridge-industrial-outline",
    MieleAppliance.FRIDGE_FREEZER: "mdi:fridge-outline",
    MieleAppliance.ROBOT_VACUUM_CLEANER: "mdi:robot-vacuum",
    MieleAppliance.WASHER_DRYER: "mdi:washing-machine",
    MieleAppliance.DISH_WARMER: "mdi:heat-wave",
    MieleAppliance.HOB_INDUCTION: "mdi:pot-steam-outline",
    MieleAppliance.STEAM_OVEN_COMBI: "mdi:chef-hat",
    MieleAppliance.WINE_CABINET: "mdi:glass-wine",
    MieleAppliance.WINE_CONDITIONING_UNIT: "mdi:glass-wine",
    MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT: "mdi:glass-wine",
    MieleAppliance.STEAM_OVEN_MICRO: "mdi:chef-hat",
    MieleAppliance.DIALOG_OVEN: "mdi:chef-hat",
    MieleAppliance.WINE_CABINET_FREEZER: "mdi:glass-wine",
    MieleAppliance.HOB_INDUCT_EXTR: "mdi:pot-steam-outline",
}


class MieleSensor(MieleEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: MieleSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)


class MieleStatusSensor(MieleSensor):
    """Representation of the status sensor."""

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, description)
        self._attr_name = None
        self._attr_icon = APPLIANCE_ICONS.get(
            MieleAppliance(self.device.device_type),
            "mdi:state-machine",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return STATE_STATUS_TAGS.get(StateStatus(self.device.state_status))

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""
        # This sensor should always be available
        return True
