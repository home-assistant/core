"""Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from pylamarzocco.const import KEYS_PER_MODEL, BoilerType, MachineModel, PhysicalKey
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LaMarzoccoConfigEntry, LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription, LaMarzoccScaleEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSensorEntityDescription(
    LaMarzoccoEntityDescription, SensorEntityDescription
):
    """Description of a La Marzocco sensor."""

    value_fn: Callable[[LaMarzoccoMachine], float | int]


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoKeySensorEntityDescription(
    LaMarzoccoEntityDescription, SensorEntityDescription
):
    """Description of a keyed La Marzocco sensor."""

    value_fn: Callable[[LaMarzoccoMachine, PhysicalKey], int | None]


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
        not in (MachineModel.LINEA_MINI, MachineModel.LINEA_MINI_R),
    ),
)

STATISTIC_ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="drink_stats_coffee",
        translation_key="drink_stats_coffee",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.statistics.total_coffee,
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription(
        key="drink_stats_flushing",
        translation_key="drink_stats_flushing",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.statistics.total_flushes,
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

KEY_STATISTIC_ENTITIES: tuple[LaMarzoccoKeySensorEntityDescription, ...] = (
    LaMarzoccoKeySensorEntityDescription(
        key="drink_stats_coffee_key",
        translation_key="drink_stats_coffee_key",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device, key: device.statistics.drink_stats.get(key),
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
            lambda coordinator: coordinator.device.model
            in (MachineModel.LINEA_MINI, MachineModel.LINEA_MINI_R)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    config_coordinator = entry.runtime_data.config_coordinator

    entities: list[LaMarzoccoSensorEntity | LaMarzoccoKeySensorEntity] = []

    entities = [
        LaMarzoccoSensorEntity(config_coordinator, description)
        for description in ENTITIES
        if description.supported_fn(config_coordinator)
    ]

    if (
        config_coordinator.device.model
        in (MachineModel.LINEA_MINI, MachineModel.LINEA_MINI_R)
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

    num_keys = KEYS_PER_MODEL[MachineModel(config_coordinator.device.model)]
    if num_keys > 0:
        entities.extend(
            LaMarzoccoKeySensorEntity(statistics_coordinator, description, key)
            for description in KEY_STATISTIC_ENTITIES
            for key in range(1, num_keys + 1)
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
    def native_value(self) -> int | float | None:
        """State of the sensor."""
        return self.entity_description.value_fn(self.coordinator.device)


class LaMarzoccoKeySensorEntity(LaMarzoccoEntity, SensorEntity):
    """Sensor for a La Marzocco key."""

    entity_description: LaMarzoccoKeySensorEntityDescription

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        description: LaMarzoccoKeySensorEntityDescription,
        key: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self.key = key
        self._attr_translation_placeholders = {"key": str(key)}
        self._attr_unique_id = f"{super()._attr_unique_id}_key{key}"

    @property
    def native_value(self) -> int | None:
        """State of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.device, PhysicalKey(self.key)
        )


class LaMarzoccoScaleSensorEntity(LaMarzoccoSensorEntity, LaMarzoccScaleEntity):
    """Sensor for a La Marzocco scale."""

    entity_description: LaMarzoccoSensorEntityDescription
