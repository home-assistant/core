"""TOLO Sauna (non-binary, general) sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tololib.message_info import SettingsInfo, StatusInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN


@dataclass
class ToloSensorEntityDescriptionBase:
    """Required values when describing TOLO Sensor entities."""

    getter: Callable[[StatusInfo], int | None]
    availability_checker: Callable[[SettingsInfo, StatusInfo], bool] | None


@dataclass
class ToloSensorEntityDescription(
    SensorEntityDescription, ToloSensorEntityDescriptionBase
):
    """Class describing TOLO Sensor entities."""

    state_class = SensorStateClass.MEASUREMENT


SENSORS = (
    ToloSensorEntityDescription(
        key="water_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:waves-arrow-up",
        name="Water Level",
        native_unit_of_measurement=PERCENTAGE,
        getter=lambda status: status.water_level_percent,
        availability_checker=None,
    ),
    ToloSensorEntityDescription(
        key="tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Tank Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        getter=lambda status: status.tank_temperature,
        availability_checker=None,
    ),
    ToloSensorEntityDescription(
        key="power_timer_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:power-settings",
        name="Power Timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        getter=lambda status: status.power_timer,
        availability_checker=lambda settings, status: status.power_on
        and settings.power_timer is not None,
    ),
    ToloSensorEntityDescription(
        key="salt_bath_timer_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:shaker-outline",
        name="Salt Bath Timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        getter=lambda status: status.salt_bath_timer,
        availability_checker=lambda settings, status: status.salt_bath_on
        and settings.salt_bath_timer is not None,
    ),
    ToloSensorEntityDescription(
        key="fan_timer_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:fan-auto",
        name="Fan Timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        getter=lambda status: status.fan_timer,
        availability_checker=lambda settings, status: status.fan_on
        and settings.fan_timer is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up (non-binary, general) sensors for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ToloSensorEntity(coordinator, entry, description) for description in SENSORS
    )


class ToloSensorEntity(ToloSaunaCoordinatorEntity, SensorEntity):
    """TOLO Number entity."""

    entity_description: ToloSensorEntityDescription

    def __init__(
        self,
        coordinator: ToloSaunaUpdateCoordinator,
        entry: ConfigEntry,
        entity_description: ToloSensorEntityDescription,
    ) -> None:
        """Initialize TOLO Number entity."""
        super().__init__(coordinator, entry)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return availability of the TOLO sensor."""
        if self.entity_description.availability_checker is None:
            return super().available
        return self.entity_description.availability_checker(
            self.coordinator.data.settings, self.coordinator.data.status
        )

    @property
    def native_value(self) -> int | None:
        """Return native value of the TOLO sensor."""
        return self.entity_description.getter(self.coordinator.data.status)
