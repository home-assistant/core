"""This platform provides binary sensors for key RainMachine data."""
from functools import partial
from typing import Callable

from regenmaschine.controller import Controller

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import RainMachineEntity
from .const import (
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DOMAIN,
)

TYPE_FLOW_SENSOR = "flow_sensor"
TYPE_FREEZE = "freeze"
TYPE_FREEZE_PROTECTION = "freeze_protection"
TYPE_HOT_DAYS = "extra_water_on_hot_days"
TYPE_HOURLY = "hourly"
TYPE_MONTH = "month"
TYPE_RAINDELAY = "raindelay"
TYPE_RAINSENSOR = "rainsensor"
TYPE_WEEKDAY = "weekday"

BINARY_SENSORS = {
    TYPE_FLOW_SENSOR: ("Flow Sensor", "mdi:water-pump", True, DATA_PROVISION_SETTINGS),
    TYPE_FREEZE: ("Freeze Restrictions", "mdi:cancel", True, DATA_RESTRICTIONS_CURRENT),
    TYPE_FREEZE_PROTECTION: (
        "Freeze Protection",
        "mdi:weather-snowy",
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
    TYPE_HOT_DAYS: (
        "Extra Water on Hot Days",
        "mdi:thermometer-lines",
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
    TYPE_HOURLY: (
        "Hourly Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
    TYPE_MONTH: ("Month Restrictions", "mdi:cancel", False, DATA_RESTRICTIONS_CURRENT),
    TYPE_RAINDELAY: (
        "Rain Delay Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
    TYPE_RAINSENSOR: (
        "Rain Sensor Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
    TYPE_WEEKDAY: (
        "Weekday Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up RainMachine binary sensors based on a config entry."""
    controller = hass.data[DOMAIN][DATA_CONTROLLER][entry.entry_id]
    coordinators = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]

    @callback
    def async_get_sensor(api_category: str) -> partial:
        """Generate the appropriate sensor object for an API category."""
        if api_category == DATA_PROVISION_SETTINGS:
            return partial(
                ProvisionSettingsBinarySensor,
                coordinators[DATA_PROVISION_SETTINGS],
            )

        if api_category == DATA_RESTRICTIONS_CURRENT:
            return partial(
                CurrentRestrictionsBinarySensor,
                coordinators[DATA_RESTRICTIONS_CURRENT],
            )

        return partial(
            UniversalRestrictionsBinarySensor,
            coordinators[DATA_RESTRICTIONS_UNIVERSAL],
        )

    async_add_entities(
        [
            async_get_sensor(api_category)(
                controller, sensor_type, name, icon, enabled_by_default
            )
            for (
                sensor_type,
                (name, icon, enabled_by_default, api_category),
            ) in BINARY_SENSORS.items()
        ]
    )


class RainMachineBinarySensor(RainMachineEntity, BinarySensorEntity):
    """Define a general RainMachine binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        sensor_type: str,
        name: str,
        icon: str,
        enabled_by_default: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, controller)
        self._enabled_by_default = enabled_by_default
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Determine whether an entity is enabled by default."""
        return self._enabled_by_default

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._unique_id}_{self._sensor_type}"


class CurrentRestrictionsBinarySensor(RainMachineBinarySensor):
    """Define a binary sensor that handles current restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._sensor_type == TYPE_FREEZE:
            self._state = self.coordinator.data["freeze"]
        elif self._sensor_type == TYPE_HOURLY:
            self._state = self.coordinator.data["hourly"]
        elif self._sensor_type == TYPE_MONTH:
            self._state = self.coordinator.data["month"]
        elif self._sensor_type == TYPE_RAINDELAY:
            self._state = self.coordinator.data["rainDelay"]
        elif self._sensor_type == TYPE_RAINSENSOR:
            self._state = self.coordinator.data["rainSensor"]
        elif self._sensor_type == TYPE_WEEKDAY:
            self._state = self.coordinator.data["weekDay"]


class ProvisionSettingsBinarySensor(RainMachineBinarySensor):
    """Define a binary sensor that handles provisioning data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._sensor_type == TYPE_FREEZE:
            self._state = self.coordinator.data["freeze"]
        elif self._sensor_type == TYPE_HOURLY:
            self._state = self.coordinator.data["hourly"]
        elif self._sensor_type == TYPE_MONTH:
            self._state = self.coordinator.data["month"]
        elif self._sensor_type == TYPE_RAINDELAY:
            self._state = self.coordinator.data["rainDelay"]
        elif self._sensor_type == TYPE_RAINSENSOR:
            self._state = self.coordinator.data["rainSensor"]
        elif self._sensor_type == TYPE_WEEKDAY:
            self._state = self.coordinator.data["weekDay"]


class UniversalRestrictionsBinarySensor(RainMachineBinarySensor):
    """Define a binary sensor that handles universal restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self._sensor_type == TYPE_FLOW_SENSOR:
            self._state = self.coordinator.data["system"].get("useFlowSensor")
