"""Sensor platform for OpenDisplay devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from opendisplay import voltage_to_percent
from opendisplay.models.advertisement import AdvertisementData
from opendisplay.models.enums import PowerMode

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenDisplayConfigEntry
from .entity import OpenDisplayEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenDisplaySensorEntityDescription(SensorEntityDescription):
    """Describes an OpenDisplay sensor entity."""

    value_fn: Callable[[AdvertisementData], float | int | None]


_TEMPERATURE_DESCRIPTION = OpenDisplaySensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda adv: adv.temperature_c,
)

_BATTERY_POWER_MODES = {PowerMode.BATTERY, PowerMode.SOLAR}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenDisplayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenDisplay sensor entities."""
    coordinator = entry.runtime_data.coordinator
    power_config = entry.runtime_data.device_config.power
    descriptions: list[OpenDisplaySensorEntityDescription] = [_TEMPERATURE_DESCRIPTION]

    if power_config.power_mode_enum in _BATTERY_POWER_MODES:
        capacity_estimator = power_config.capacity_estimator
        descriptions += [
            OpenDisplaySensorEntityDescription(
                key="battery_voltage",
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_registry_enabled_default=False,
                value_fn=lambda adv: adv.battery_mv,
            ),
            OpenDisplaySensorEntityDescription(
                key="battery",
                device_class=SensorDeviceClass.BATTERY,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                value_fn=lambda adv: voltage_to_percent(
                    adv.battery_mv, capacity_estimator
                ),
            ),
        ]

    async_add_entities(
        OpenDisplaySensorEntity(coordinator, entry, description)
        for description in descriptions
    )


class OpenDisplaySensorEntity(OpenDisplayEntity, SensorEntity):
    """A sensor entity for an OpenDisplay device."""

    entity_description: OpenDisplaySensorEntityDescription

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data.advertisement)
