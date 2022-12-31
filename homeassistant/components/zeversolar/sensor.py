"""Support for the Zeversolar platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import ZeversolarCoordinator
from .entity import ZeversolarEntity


@dataclass
class ZeversolarEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[zeversolar.ZeverSolarData], Any]


@dataclass
class ZeversolarEntityDescription(
    SensorEntityDescription, ZeversolarEntityDescriptionMixin
):
    """Describes Zeversolar sensor entity."""


SENSOR_TYPES = (
    ZeverSolarEntityDescription(
        key="pac",
        name="Current power",
        icon="mdi:solar-power-variant",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.pac,
    ),
    ZeverSolarEntityDescription(
        key="energy_today",
        name="Energy today",
        icon="mdi:home-battery",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.energy_today,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ZeverSolar sensor."""
    coordinator: ZeversolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZeversolarSensor(
            device_id=entry.data[CONF_IP_ADDRESS],
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
        device_id: str,
        description: ZeversolarEntityDescription,
        coordinator: ZeversolarCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(
            device_id=device_id,
            coordinator=coordinator,
        )
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
