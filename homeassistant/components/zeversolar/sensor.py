"""Support for the Zeversolar platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import zeversolar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZeversolarCoordinator
from .entity import ZeversolarEntity


@dataclass(frozen=True, kw_only=True)
class ZeversolarEntityDescription(SensorEntityDescription):
    """Describes Zeversolar sensor entity."""

    value_fn: Callable[[zeversolar.ZeverSolarData], zeversolar.kWh | zeversolar.Watt]


SENSOR_TYPES = (
    ZeversolarEntityDescription(
        key="pac",
        translation_key="pac",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.pac,
    ),
    ZeversolarEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.energy_today,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Zeversolar sensor."""
    coordinator: ZeversolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZeversolarSensor(
            description=description,
            coordinator=coordinator,
        )
        for description in SENSOR_TYPES
    )


class ZeversolarSensor(ZeversolarEntity, SensorEntity):
    """Implementation of the Zeversolar sensor."""

    entity_description: ZeversolarEntityDescription

    def __init__(
        self,
        *,
        description: ZeversolarEntityDescription,
        coordinator: ZeversolarCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.serial_number}_{description.key}"

    @property
    def native_value(self) -> int | float:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
