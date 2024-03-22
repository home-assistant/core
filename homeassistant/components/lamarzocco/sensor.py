"""Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from lmcloud.const import BoilerType, PhysicalKey
from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import _DeviceT
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSensorEntityDescription(
    LaMarzoccoEntityDescription, SensorEntityDescription, Generic[_DeviceT]
):
    """Description of a La Marzocco sensor."""

    value_fn: Callable[[_DeviceT], float | int]


ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription[LaMarzoccoMachine](
        key="drink_stats_coffee",
        translation_key="drink_stats_coffee",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.statistics.drink_stats.get(PhysicalKey.A, 0),
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription[LaMarzoccoMachine](
        key="drink_stats_flushing",
        translation_key="drink_stats_flushing",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.statistics.total_flushes,
        available_fn=lambda device: len(device.statistics.drink_stats) > 0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription[LaMarzoccoMachine](
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
    LaMarzoccoSensorEntityDescription[LaMarzoccoMachine](
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
    LaMarzoccoSensorEntityDescription[LaMarzoccoMachine](
        key="current_temp_steam",
        translation_key="current_temp_steam",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda device: device.config.boilers[
            BoilerType.STEAM
        ].current_temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoSensorEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoSensorEntity(LaMarzoccoEntity, SensorEntity):
    """Sensor representing espresso machine temperature data."""

    entity_description: LaMarzoccoSensorEntityDescription

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(self.coordinator.device)
