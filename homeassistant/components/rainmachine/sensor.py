"""This platform provides support for sensor data from RainMachine."""
from functools import partial

from regenmaschine.controller import Controller

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, VOLUME_CUBIC_METERS
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

SENSORS = {
    TYPE_FLOW_SENSOR_CLICK_M3: (
        "Flow Sensor Clicks",
        "mdi:water-pump",
        f"clicks/{VOLUME_CUBIC_METERS}",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_CONSUMED_LITERS: (
        "Flow Sensor Consumed Liters",
        "mdi:water-pump",
        "liter",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_START_INDEX: (
        "Flow Sensor Start Index",
        "mdi:water-pump",
        "index",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_WATERING_CLICKS: (
        "Flow Sensor Clicks",
        "mdi:water-pump",
        "clicks",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FREEZE_TEMP: (
        "Freeze Protect Temperature",
        "mdi:thermometer",
        TEMP_CELSIUS,
        "temperature",
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
}


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
            async_get_sensor(api_category)(
                controller,
                sensor_type,
                name,
                icon,
                unit,
                device_class,
                enabled_by_default,
            )
            for (
                sensor_type,
                (name, icon, unit, device_class, enabled_by_default, api_category),
            ) in SENSORS.items()
        ]
    )


class RainMachineSensor(RainMachineEntity, SensorEntity):
    """Define a general RainMachine sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        sensor_type: str,
        name: str,
        icon: str,
        unit: str,
        device_class: str,
        enabled_by_default: bool,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, controller)
        self._device_class = device_class
        self._enabled_by_default = enabled_by_default
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Determine whether an entity is enabled by default."""
        return self._enabled_by_default

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def state(self) -> str:
        """Return the name of the entity."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._unique_id}_{self._sensor_type}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        return self._unit


class ProvisionSettingsSensor(RainMachineSensor):
    """Define a sensor that handles provisioning data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._sensor_type == TYPE_FLOW_SENSOR_CLICK_M3:
            self._state = self.coordinator.data["system"].get(
                "flowSensorClicksPerCubicMeter"
            )
        elif self._sensor_type == TYPE_FLOW_SENSOR_CONSUMED_LITERS:
            clicks = self.coordinator.data["system"].get("flowSensorWateringClicks")
            clicks_per_m3 = self.coordinator.data["system"].get(
                "flowSensorClicksPerCubicMeter"
            )

            if clicks and clicks_per_m3:
                self._state = (clicks * 1000) / clicks_per_m3
            else:
                self._state = None
        elif self._sensor_type == TYPE_FLOW_SENSOR_START_INDEX:
            self._state = self.coordinator.data["system"].get("flowSensorStartIndex")
        elif self._sensor_type == TYPE_FLOW_SENSOR_WATERING_CLICKS:
            self._state = self.coordinator.data["system"].get(
                "flowSensorWateringClicks"
            )


class UniversalRestrictionsSensor(RainMachineSensor):
    """Define a sensor that handles universal restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._sensor_type == TYPE_FREEZE_TEMP:
            self._state = self.coordinator.data["freezeProtectTemp"]
