"""Hanna Instruments sensor integration for Home Assistant.

This module provides sensor entities for various Hanna Instruments devices,
including pH, ORP, temperature, and chemical sensors. It uses the Hanna API
to fetch readings and updates them periodically.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HannaConfigEntry, HannaDataCoordinator
from .entity import HannaEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="orp",
        translation_key="chlorine_orp_value",
        icon="mdi:flask",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp",
        translation_key="water_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="airTemp",
        translation_key="air_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="acidBase",
        translation_key="ph_acid_base_flow_rate",
        icon="mdi:chemical-weapon",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="cl",
        translation_key="chlorine_flow_rate",
        icon="mdi:chemical-weapon",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HannaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hanna sensors from a config entry."""
    device_coordinators = entry.runtime_data

    async_add_entities(
        HannaSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        for coordinator in device_coordinators.values()
    )


class HannaSensor(HannaEntity, SensorEntity):
    """Representation of a Hanna sensor."""

    def __init__(
        self,
        coordinator: HannaDataCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Hanna sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_identifier}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon
        self._attr_state_class = description.state_class
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self.description = description

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.get_parameter_value(self.description.key)
