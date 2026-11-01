"""Sensor platform for Kingspan Watchman SENSiT."""

# pylint: disable=unexpected-keyword-arg

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import logging
from typing import override

from connectsensor.analysis import TankData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_OIL_ENERGY_DENSITY, DEFAULT_OIL_ENERGY_DENSITY
from .coordinator import SENSiTConfigEntry
from .entity import SENSiTEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

PARALLEL_UPDATES = 0


def _get_energy_density(config_entry: SENSiTConfigEntry) -> float:
    """Return configured oil energy density."""
    return float(
        config_entry.options.get(
            CONF_OIL_ENERGY_DENSITY,
            config_entry.data.get(
                CONF_OIL_ENERGY_DENSITY,
                DEFAULT_OIL_ENERGY_DENSITY,
            ),
        )
    )


@dataclass(frozen=True, kw_only=True)
class SENSiTSensorEntityDescription(SensorEntityDescription):
    """Describes a Kingspan Watchman SENSiT sensor entity."""

    value_fn: Callable[
        [TankData, SENSiTConfigEntry], float | int | Decimal | datetime | None
    ]


SENSOR_DESCRIPTIONS: tuple[SENSiTSensorEntityDescription, ...] = (
    SENSiTSensorEntityDescription(
        key="oil_level",
        translation_key="oil_level",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda tank, _: tank.level,
    ),
    SENSiTSensorEntityDescription(
        key="tank_percentage_full",
        translation_key="tank_percentage_full",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda tank, _: (
            Decimal(f"{100 * (tank.level / tank.capacity):.1f}")
            if tank.capacity > 0
            else Decimal("0.0")
        ),
    ),
    SENSiTSensorEntityDescription(
        key="tank_capacity",
        translation_key="tank_capacity",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda tank, _: tank.capacity,
    ),
    SENSiTSensorEntityDescription(
        key="last_reading_date",
        translation_key="last_reading_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda tank, _: tank.last_read,
    ),
    SENSiTSensorEntityDescription(
        key="current_usage",
        translation_key="current_usage",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda tank, _: Decimal(f"{(tank.usage_rate / 24):.1f}"),
    ),
    SENSiTSensorEntityDescription(
        key="forecast_empty",
        translation_key="forecast_empty",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda tank, _: tank.forecast_empty,
    ),
    SENSiTSensorEntityDescription(
        key="current_energy_usage",
        translation_key="current_energy_usage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=1,
        value_fn=lambda tank, entry: round(
            float((tank.usage_rate / 24) * _get_energy_density(entry)), 1
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: SENSiTConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform and listen for new dynamically added tanks."""
    coordinator = config_entry.runtime_data
    added_tanks: set[str] = set()

    @callback
    def async_add_new_tanks() -> None:
        new_entities: list[SENSiTEntity] = []
        for tank in coordinator.data:
            if tank.serial_number not in added_tanks:
                added_tanks.add(tank.serial_number)
                new_entities.extend(
                    SENSiTSensor(
                        coordinator, config_entry, tank.serial_number, description
                    )
                    for description in SENSOR_DESCRIPTIONS
                )
        if new_entities:
            async_add_entities(new_entities)

    async_add_new_tanks()
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_tanks))


class SENSiTSensor(SENSiTEntity, SensorEntity):
    """Representation of a Kingspan Watchman SENSiT sensor."""

    entity_description: SENSiTSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | int | Decimal | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.tank_data, self.config_entry)
