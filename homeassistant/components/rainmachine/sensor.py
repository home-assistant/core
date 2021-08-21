"""This platform provides support for sensor data from RainMachine."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from regenmaschine.controller import Controller

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import RainMachineEntity
from .const import (
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_UNIVERSAL,
    DOMAIN,
)

TYPE_FLOW_SENSOR_CLICK_M3 = "flow_sensor_clicks_cubic_meter"
TYPE_FLOW_SENSOR_CONSUMED_LITERS = "flow_sensor_consumed_liters"
TYPE_FLOW_SENSOR_START_INDEX = "flow_sensor_start_index"
TYPE_FLOW_SENSOR_WATERING_CLICKS = "flow_sensor_watering_clicks"
TYPE_FREEZE_TEMP = "freeze_protect_temp"


@dataclass
class RainmachineRequiredKeysMixin:
    """Mixin for required keys."""

    api_category: str


@dataclass
class RainmachineSensorEntityDescription(
    SensorEntityDescription, RainmachineRequiredKeysMixin
):
    """Describes Rainmachine sensor entity."""


SENSOR_TYPES: tuple[RainmachineSensorEntityDescription, ...] = (
    RainmachineSensorEntityDescription(
        key=TYPE_FLOW_SENSOR_CLICK_M3,
        name="Flow Sensor Clicks",
        icon="mdi:water-pump",
        native_unit_of_measurement=f"clicks/{VOLUME_CUBIC_METERS}",
        entity_registry_enabled_default=False,
        api_category=DATA_PROVISION_SETTINGS,
    ),
    RainmachineSensorEntityDescription(
        key=TYPE_FLOW_SENSOR_CONSUMED_LITERS,
        name="Flow Sensor Consumed Liters",
        icon="mdi:water-pump",
        native_unit_of_measurement="liter",
        entity_registry_enabled_default=False,
        api_category=DATA_PROVISION_SETTINGS,
    ),
    RainmachineSensorEntityDescription(
        key=TYPE_FLOW_SENSOR_START_INDEX,
        name="Flow Sensor Start Index",
        icon="mdi:water-pump",
        native_unit_of_measurement="index",
        entity_registry_enabled_default=False,
        api_category=DATA_PROVISION_SETTINGS,
    ),
    RainmachineSensorEntityDescription(
        key=TYPE_FLOW_SENSOR_WATERING_CLICKS,
        name="Flow Sensor Clicks",
        icon="mdi:water-pump",
        native_unit_of_measurement="clicks",
        entity_registry_enabled_default=False,
        api_category=DATA_PROVISION_SETTINGS,
    ),
    TYPE_FREEZE_TEMP: (
        "Freeze Protect Temperature",
        "mdi:thermometer",
        TEMP_CELSIUS,
        DEVICE_CLASS_TEMPERATURE,
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine sensors based on a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id]
    coordinators = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    @callback
    def async_get_sensor(api_category: str) -> partial:
        """Generate the appropriate sensor object for an API category."""
        if api_category == DATA_PROVISION_SETTINGS:
            return partial(
                ProvisionSettingsSensor,
                coordinators[DATA_PROVISION_SETTINGS],
            )

        return partial(
            UniversalRestrictionsSensor,
            coordinators[DATA_RESTRICTIONS_UNIVERSAL],
        )

    async_add_entities(
        [
            async_get_sensor(description.api_category)(controller, description)
            for description in SENSOR_TYPES
        ]
    )


class RainMachineSensor(RainMachineEntity, SensorEntity):
    """Define a general RainMachine sensor."""

    entity_description: RainmachineSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        description: RainmachineSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, controller, sensor_type)

        self._attr_device_class = device_class
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._attr_icon = icon
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit


class ProvisionSettingsSensor(RainMachineSensor):
    """Define a sensor that handles provisioning data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._entity_type == TYPE_FLOW_SENSOR_CLICK_M3:
            self._attr_native_value = self.coordinator.data["system"].get(
                "flowSensorClicksPerCubicMeter"
            )
        elif self._entity_type == TYPE_FLOW_SENSOR_CONSUMED_LITERS:
            clicks = self.coordinator.data["system"].get("flowSensorWateringClicks")
            clicks_per_m3 = self.coordinator.data["system"].get(
                "flowSensorClicksPerCubicMeter"
            )

            if clicks and clicks_per_m3:
                self._attr_native_value = (clicks * 1000) / clicks_per_m3
            else:
                self._attr_native_value = None
        elif self._entity_type == TYPE_FLOW_SENSOR_START_INDEX:
            self._attr_native_value = self.coordinator.data["system"].get(
                "flowSensorStartIndex"
            )
        elif self._entity_type == TYPE_FLOW_SENSOR_WATERING_CLICKS:
            self._attr_native_value = self.coordinator.data["system"].get(
                "flowSensorWateringClicks"
            )


class UniversalRestrictionsSensor(RainMachineSensor):
    """Define a sensor that handles universal restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._entity_type == TYPE_FREEZE_TEMP:
            self._attr_native_value = self.coordinator.data["freezeProtectTemp"]
