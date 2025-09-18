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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HannaDataCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = {
    "ph": SensorEntityDescription(
        key="ph",
        name="pH value",
        icon="mdi:flask",
        device_class=SensorDeviceClass.PH,
    ),
    "orp": SensorEntityDescription(
        key="orp",
        name="Chlorine ORP value",
        icon="mdi:flask",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    "temp": SensorEntityDescription(
        key="temp",
        name="Water temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "airTemp": SensorEntityDescription(
        key="airTemp",
        name="Air temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "acidBase": SensorEntityDescription(
        key="acidBase", name="pH Acid/Base flow rate", icon="mdi:chemical-weapon"
    ),
    "cl": SensorEntityDescription(
        key="cl", name="Chlorine flow rate", icon="mdi:chemical-weapon"
    ),
    "alarms": SensorEntityDescription(
        key="alarms",
        name="Alarms",
        icon="mdi:alert",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hanna sensors from a config entry."""
    device_coordinators = entry.runtime_data

    # Collect all entities during initialization
    all_entities: list[HannaParamSensor | HannaAlarmSensor] = []

    for coordinator in device_coordinators.values():
        # Add parameter sensors
        for parameter in coordinator.get_parameters():
            if description := SENSOR_DESCRIPTIONS.get(parameter["name"]):
                all_entities.append(HannaParamSensor(coordinator, description))
            else:
                _LOGGER.warning("No sensor description found for %s", parameter["name"])

        # Add alarms sensor
        all_entities.append(
            HannaAlarmSensor(coordinator, SENSOR_DESCRIPTIONS["alarms"])
        )

    if all_entities:
        async_add_entities(all_entities)


class HannaSensor(CoordinatorEntity[HannaDataCoordinator], SensorEntity):
    """Representation of a Hanna sensor."""

    def __init__(
        self, coordinator: HannaDataCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Hanna sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_identifier}_{description.key}"
        self._attr_name = (
            None
            if description.name is None or description.name is UNDEFINED
            else description.name
        )
        self._attr_icon = description.icon
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self.description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.device_info


class HannaParamSensor(HannaSensor):
    """Representation of a Hanna sensor."""

    def __init__(
        self, coordinator: HannaDataCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Hanna sensor."""
        super().__init__(coordinator, description)
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = description.device_class

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.get_parameter_value(self.description.key)


class HannaAlarmSensor(HannaSensor):
    """Representation of a Hanna alarm sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        alarms = self.coordinator.get_all_alarms()
        if not alarms:
            return "No alarms"
        return ", ".join(sorted(alarms))
