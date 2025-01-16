"""Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from pylamarzocco.const import BoilerType, MachineModel, PhysicalKey
from pylamarzocco.devices.machine import LaMarzoccoMachine

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription, LaMarzoccScaleEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSensorEntityDescription(
    LaMarzoccoEntityDescription, SensorEntityDescription
):
    """Description of a La Marzocco sensor."""

    value_fn: Callable[[LaMarzoccoMachine], float | int]


ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="shot_timer",
        translation_key="shot_timer",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda device: device.config.brew_active_duration,
        available_fn=lambda device: device.websocket_connected,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda coordinator: coordinator.local_connection_configured,
    ),
    LaMarzoccoSensorEntityDescription(
        key="current_temp_coffee",
        translation_key="current_temp_coffee",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda device: device.config.boilers[
            BoilerType.COFFEE
        ].current_temperature,
    ),
    LaMarzoccoSensorEntityDescription(
        key="current_temp_steam",
        translation_key="current_temp_steam",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda device: device.config.boilers[
            BoilerType.STEAM
        ].current_temperature,
        supported_fn=lambda coordinator: coordinator.device.model
        != MachineModel.LINEA_MINI,
    ),
)

STATISTIC_ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="drink_stats_coffee",
        translation_key="drink_stats_coffee",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.statistics.drink_stats.get(PhysicalKey.A, 0),
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription(
        key="drink_stats_flushing",
        translation_key="drink_stats_flushing",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.statistics.total_flushes,
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SCALE_ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="scale_battery",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda device: (
            device.config.scale.battery if device.config.scale else 0
        ),
        supported_fn=(
            lambda coordinator: coordinator.device.model == MachineModel.LINEA_MINI
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    config_coordinator = entry.runtime_data.config_coordinator

    entities = [
        LaMarzoccoSensorEntity(config_coordinator, description)
        for description in ENTITIES
        if description.supported_fn(config_coordinator)
    ]

    if (
        config_coordinator.device.model == MachineModel.LINEA_MINI
        and config_coordinator.device.config.scale
    ):
        entities.extend(
            LaMarzoccoScaleSensorEntity(config_coordinator, description)
            for description in SCALE_ENTITIES
        )

    statistics_coordinator = entry.runtime_data.statistics_coordinator
    entities.extend(
        LaMarzoccoSensorEntity(statistics_coordinator, description)
        for description in STATISTIC_ENTITIES
        if description.supported_fn(statistics_coordinator)
    )

    def _async_add_new_scale() -> None:
        async_add_entities(
            LaMarzoccoScaleSensorEntity(config_coordinator, description)
            for description in SCALE_ENTITIES
        )

    config_coordinator.new_device_callback.append(_async_add_new_scale)

    async_add_entities(entities)


class LaMarzoccoSensorEntity(LaMarzoccoEntity, SensorEntity):
    """Sensor representing espresso machine temperature data."""

    entity_description: LaMarzoccoSensorEntityDescription

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(self.coordinator.device)


class LaMarzoccoScaleSensorEntity(LaMarzoccoSensorEntity, LaMarzoccScaleEntity):
    """Sensor for a La Marzocco scale."""

    entity_description: LaMarzoccoSensorEntityDescription
