"""Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from pylamarzocco.const import ModelName, WidgetType
from pylamarzocco.models import (
    BackFlush,
    BaseWidgetOutput,
    CoffeeBoiler,
    SteamBoilerLevel,
    SteamBoilerTemperature,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSensorEntityDescription(
    LaMarzoccoEntityDescription,
    SensorEntityDescription,
):
    """Description of a La Marzocco sensor."""

    value_fn: Callable[
        [dict[WidgetType, BaseWidgetOutput]], StateType | datetime | None
    ]


ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="coffee_boiler_ready_time",
        translation_key="coffee_boiler_ready_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=(
            lambda config: cast(
                CoffeeBoiler, config[WidgetType.CM_COFFEE_BOILER]
            ).ready_start_time
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription(
        key="steam_boiler_ready_time",
        translation_key="steam_boiler_ready_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=(
            lambda config: cast(
                SteamBoilerLevel, config[WidgetType.CM_STEAM_BOILER_LEVEL]
            ).ready_start_time
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (ModelName.LINEA_MICRA, ModelName.LINEA_MINI_R)
        ),
    ),
    LaMarzoccoSensorEntityDescription(
        key="steam_boiler_ready_time",
        translation_key="steam_boiler_ready_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=(
            lambda config: cast(
                SteamBoilerTemperature, config[WidgetType.CM_STEAM_BOILER_TEMPERATURE]
            ).ready_start_time
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (ModelName.GS3_AV, ModelName.GS3_MP, ModelName.LINEA_MINI)
        ),
    ),
    LaMarzoccoSensorEntityDescription(
        key="last_cleaning_time",
        translation_key="last_cleaning_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=(
            lambda config: cast(
                BackFlush, config[WidgetType.CM_BACK_FLUSH]
            ).last_cleaning_start_time
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = entry.runtime_data.config_coordinator

    async_add_entities(
        LaMarzoccoSensorEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoSensorEntity(LaMarzoccoEntity, SensorEntity):
    """Sensor representing espresso machine water reservoir status."""

    entity_description: LaMarzoccoSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return  value of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.device.dashboard.config
        )
