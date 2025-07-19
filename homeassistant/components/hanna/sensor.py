"""Hanna Instruments sensor integration for Home Assistant.

This module provides sensor entities for various Hanna Instruments devices,
including pH, ORP, temperature, and chemical sensors. It uses the Hanna API
to fetch readings and updates them periodically.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

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
from homeassistant.helpers.typing import UNDEFINED

from .coordinator import HannaDataCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = {
    "ph": SensorEntityDescription(
        key="ph",
        name="pH value",
        icon="mdi:water",
        device_class=SensorDeviceClass.PH,
    ),
    "orp": SensorEntityDescription(
        key="orp",
        name="Chlorine ORP value",
        icon="mdi:flash",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    "temp": SensorEntityDescription(
        key="temp",
        name="Water Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "airTemp": SensorEntityDescription(
        key="airTemp",
        name="Air Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "acidBase": SensorEntityDescription(
        key="acidBase", name="pH Acid/Base Flow Rate", icon="mdi:flask"
    ),
    "cl": SensorEntityDescription(
        key="cl", name="Chlorine Flow Rate", icon="mdi:chemical-weapon"
    ),
    "phPumpColor": SensorEntityDescription(
        key="phPumpColor",
        name="pH Pump Status",
        icon="mdi:pump",
    ),
    "clPumpColor": SensorEntityDescription(
        key="clPumpColor",
        name="Chlorine Pump Status",
        icon="mdi:pump",
    ),
    "StatusColor": SensorEntityDescription(
        key="StatusColor",
        name="System Status",
        icon="mdi:information",
    ),
    "ServiceColor": SensorEntityDescription(
        key="ServiceColor",
        name="Service Status",
        icon="mdi:wrench",
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
    device_coordinators = entry.runtime_data["device_coordinators"]

    # Collect all entities during initialization
    all_entities: list[HannaParamSensor | HannaStatusSensor | HannaAlarmSensor] = []

    for coordinator in device_coordinators.values():
        if not coordinator.readings:
            _LOGGER.warning("No data received for %s", coordinator.device_identifier)
            continue

        # Add parameter sensors
        for parameter in coordinator.get_parameters():
            if description := SENSOR_DESCRIPTIONS.get(parameter["name"]):
                all_entities.append(HannaParamSensor(coordinator, description))
            else:
                _LOGGER.warning("No sensor description found for %s", parameter["name"])

        # Add status sensors
        for sensor_name in coordinator.get_messages_value("status"):
            if description := SENSOR_DESCRIPTIONS.get(sensor_name):
                all_entities.append(HannaStatusSensor(coordinator, description))
            else:
                _LOGGER.warning("No sensor description found for %s", sensor_name)

        # Add alarms sensor
        all_entities.append(
            HannaAlarmSensor(coordinator, SENSOR_DESCRIPTIONS["alarms"])
        )

    # Add all entities at once
    if all_entities:
        async_add_entities(all_entities)


class HannaSensor(SensorEntity):
    """Representation of a Hanna sensor."""

    def __init__(
        self, coordinator: HannaDataCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Hanna sensor."""
        self._attr_unique_id = f"{coordinator.device_identifier}_{description.key}"
        self._attr_name = (
            None
            if description.name is None or description.name is UNDEFINED
            else description.name
        )
        self._attr_native_value = None
        self._attr_icon = description.icon
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self.description = description
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class HannaParamSensor(HannaSensor):
    """Representation of a Hanna sensor."""

    def __init__(
        self, coordinator: HannaDataCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Hanna sensor."""
        super().__init__(coordinator, description)

        self._attr_native_value = coordinator.get_parameter_value(description.key)
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = description.device_class

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        attrs = {"last_updated": self.coordinator.get_last_update_time()}

        # Add ORP calibration data if this is an ORP sensor
        if self.description.key == "orp":
            glp_data = self.coordinator.readings.get("messages", {}).get("glp", {})
            attrs.update(
                {
                    "last_calibration": glp_data.get("orpDateTime"),
                    "offset": glp_data.get("orpOffset"),
                    "calibration_point": glp_data.get("orp"),
                }
            )
        # Add pH calibration data if this is a pH sensor
        elif self.description.key == "ph":
            glp_data = self.coordinator.readings.get("messages", {}).get("glp", {})
            attrs.update(
                {
                    "last_calibration": glp_data.get("pHDateTime"),
                    "offset": glp_data.get("pHOffset"),
                    "slope": glp_data.get("pHSlope"),
                    "calibration_point_1_ph": glp_data.get("pH1"),
                    "calibration_point_1_mv": glp_data.get("mV1"),
                    "calibration_point_1_temperature": glp_data.get("temp1"),
                    "calibration_point_2_ph": glp_data.get("pH2"),
                    "calibration_point_2_mv": glp_data.get("mV2"),
                    "calibration_point_2_temperature": glp_data.get("temp2"),
                }
            )

        return attrs

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self.coordinator.get_parameter_value(self.description.key)
        if value is not None:
            self._attr_native_value = value
            self.async_write_ha_state()


class HannaStatusSensor(HannaSensor):
    """Representation of a Hanna status sensor."""

    def __init__(
        self, coordinator: HannaDataCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Hanna status sensor."""
        super().__init__(coordinator, description)
        self._attr_native_value = coordinator.get_messages_value("status").get(
            self.description.key
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        return {"last_updated": self.coordinator.get_last_update_time()}

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self.coordinator.get_messages_value("status").get(self.description.key)
        if value is not None:
            self._attr_native_value = value
            self.async_write_ha_state()


class HannaAlarmSensor(HannaSensor):
    """Representation of a Hanna alarm sensor."""

    def __init__(
        self,
        coordinator: HannaDataCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Hanna alarm sensor."""
        super().__init__(coordinator, description)
        self._attr_native_value = self._get_alarm_state(coordinator.readings)

    def _get_alarm_state(self, readings: dict) -> str:
        """Get the current alarm state."""
        alarms = readings.get("messages", {}).get("alarms", [])
        if not alarms:
            return "No Alarms"
        return ", ".join(alarms)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        return {
            "last_updated": self.coordinator.get_last_update_time(),
            "alarms": self.coordinator.get_messages_value("alarms"),
            "warnings": self.coordinator.get_messages_value("warnings"),
            "errors": self.coordinator.get_messages_value("errors"),
        }

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self._get_alarm_state(self.coordinator.readings)
        if value is not None:
            self._attr_native_value = value
            self.async_write_ha_state()
