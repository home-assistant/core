"""Vacuum platform for Dyson."""
from __future__ import annotations

from typing import Callable

from libdyson import VacuumEyePowerMode, VacuumState

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_FAN_SPEED,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    StateVacuumEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_PAUSED
from homeassistant.core import HomeAssistant

from . import DysonEntity
from .const import DATA_DEVICES, DOMAIN

SUPPORTED_FEATURES = (
    SUPPORT_START
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_FAN_SPEED
    | SUPPORT_STATUS
    | SUPPORT_STATE
    | SUPPORT_BATTERY
)

DYSON_STATUS = {
    VacuumState.FAULT_CALL_HELPLINE: "Error: Call helpline",
    VacuumState.FAULT_CONTACT_HELPLINE: "Error: Contact helpline",
    VacuumState.FAULT_CRITICAL: "Error: Critical",
    VacuumState.FAULT_GETTING_INFO: "Error: Getting info",
    VacuumState.FAULT_LOST: "Error: Lost",
    VacuumState.FAULT_ON_DOCK: "Error: On dock",
    VacuumState.FAULT_ON_DOCK_CHARGED: "Error: On dock charged",
    VacuumState.FAULT_ON_DOCK_CHARGING: "Error: On dock charging",
    VacuumState.FAULT_REPLACE_ON_DOCK: "Error: Replace device on dock",
    VacuumState.FAULT_RETURN_TO_DOCK: "Error: Return to dock",
    VacuumState.FAULT_RUNNING_DIAGNOSTIC: "Error: Running diagnostic",
    VacuumState.FAULT_USER_RECOVERABLE: "Error: Blocked",
    VacuumState.FULL_CLEAN_ABANDONED: "Abandoned",
    VacuumState.FULL_CLEAN_ABORTED: "Returning home",
    VacuumState.FULL_CLEAN_CHARGING: "Charging",
    VacuumState.FULL_CLEAN_DISCOVERING: "Discovering",
    VacuumState.FULL_CLEAN_FINISHED: "Finished",
    VacuumState.FULL_CLEAN_INITIATED: "Initiated",
    VacuumState.FULL_CLEAN_NEEDS_CHARGE: "Need charging",
    VacuumState.FULL_CLEAN_PAUSED: "Paused",
    VacuumState.FULL_CLEAN_RUNNING: "Cleaning",
    VacuumState.FULL_CLEAN_TRAVERSING: "Traversing",
    VacuumState.INACTIVE_CHARGED: "Stopped - Charged",
    VacuumState.INACTIVE_CHARGING: "Stopped - Charging",
    VacuumState.INACTIVE_DISCHARGING: "Stopped - Discharging",
    VacuumState.MAPPING_ABORTED: "Mapping - Returning home",
    VacuumState.MAPPING_CHARGING: "Mapping - Charging",
    VacuumState.MAPPING_FINISHED: "Mapping - Finished",
    VacuumState.MAPPING_INITIATED: "Mapping - Initiated",
    VacuumState.MAPPING_NEEDS_CHARGE: "Mapping - Needs charging",
    VacuumState.MAPPING_PAUSED: "Mapping - Paused",
    VacuumState.MAPPING_RUNNING: "Mapping - Running",
}

DYSON_STATES = {
    VacuumState.FAULT_CALL_HELPLINE: STATE_ERROR,
    VacuumState.FAULT_CONTACT_HELPLINE: STATE_ERROR,
    VacuumState.FAULT_CRITICAL: STATE_ERROR,
    VacuumState.FAULT_GETTING_INFO: STATE_ERROR,
    VacuumState.FAULT_LOST: STATE_ERROR,
    VacuumState.FAULT_ON_DOCK: STATE_ERROR,
    VacuumState.FAULT_ON_DOCK_CHARGED: STATE_ERROR,
    VacuumState.FAULT_ON_DOCK_CHARGING: STATE_ERROR,
    VacuumState.FAULT_REPLACE_ON_DOCK: STATE_ERROR,
    VacuumState.FAULT_RETURN_TO_DOCK: STATE_ERROR,
    VacuumState.FAULT_RUNNING_DIAGNOSTIC: STATE_ERROR,
    VacuumState.FAULT_USER_RECOVERABLE: STATE_ERROR,
    VacuumState.FULL_CLEAN_ABANDONED: STATE_RETURNING,
    VacuumState.FULL_CLEAN_ABORTED: STATE_RETURNING,
    VacuumState.FULL_CLEAN_CHARGING: STATE_DOCKED,
    VacuumState.FULL_CLEAN_DISCOVERING: STATE_CLEANING,
    VacuumState.FULL_CLEAN_FINISHED: STATE_DOCKED,
    VacuumState.FULL_CLEAN_INITIATED: STATE_CLEANING,
    VacuumState.FULL_CLEAN_NEEDS_CHARGE: STATE_RETURNING,
    VacuumState.FULL_CLEAN_PAUSED: STATE_PAUSED,
    VacuumState.FULL_CLEAN_RUNNING: STATE_CLEANING,
    VacuumState.FULL_CLEAN_TRAVERSING: STATE_CLEANING,
    VacuumState.INACTIVE_CHARGED: STATE_DOCKED,
    VacuumState.INACTIVE_CHARGING: STATE_DOCKED,
    VacuumState.INACTIVE_DISCHARGING: STATE_DOCKED,
    VacuumState.MAPPING_ABORTED: STATE_RETURNING,
    VacuumState.MAPPING_CHARGING: STATE_PAUSED,
    VacuumState.MAPPING_FINISHED: STATE_CLEANING,
    VacuumState.MAPPING_INITIATED: STATE_CLEANING,
    VacuumState.MAPPING_NEEDS_CHARGE: STATE_RETURNING,
    VacuumState.MAPPING_PAUSED: STATE_PAUSED,
    VacuumState.MAPPING_RUNNING: STATE_CLEANING,
}

EYE_POWER_MODE_ENUM_TO_STR = {
    VacuumEyePowerMode.QUIET: "Quiet",
    VacuumEyePowerMode.MAX: "Max",
}
EYE_POWER_MODE_STR_TO_ENUM = {
    value: key for key, value in EYE_POWER_MODE_ENUM_TO_STR.items()
}

ATTR_POSITION = "position"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Dyson vacuum from a config entry."""
    device = hass.data[DOMAIN][DATA_DEVICES][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]
    entity = Dyson360EyeEntity(device, name)
    async_add_entities([entity])


class DysonVacuumEntity(DysonEntity, StateVacuumEntity):
    """Dyson vacuum entity base class."""

    @property
    def state(self) -> str:
        """Return the state of the vacuum."""
        return DYSON_STATES[self._device.state]

    @property
    def status(self) -> str:
        """Return the status of the vacuum."""
        return DYSON_STATUS[self._device.state]

    @property
    def battery_level(self) -> int:
        """Return the battery level of the vacuum cleaner."""
        return self._device.battery_level

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_connected

    @property
    def supported_features(self) -> int:
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORTED_FEATURES

    @property
    def device_state_attributes(self) -> dict:
        """Expose the status to state attributes."""
        return {
            ATTR_POSITION: str(self._device.position),
            ATTR_STATUS: self.status,
        }

    def pause(self) -> None:
        """Pause the device."""
        self._device.pause()

    def return_to_base(self, **kwargs) -> None:
        """Return the device to base."""
        self._device.abort()


class Dyson360EyeEntity(DysonVacuumEntity):
    """Dyson 360 Eye robot vacuum entity."""

    @property
    def fan_speed(self) -> str:
        """Return the fan speed of the vacuum cleaner."""
        return EYE_POWER_MODE_ENUM_TO_STR[self._device.power_mode]

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(EYE_POWER_MODE_STR_TO_ENUM.keys())

    def start(self) -> None:
        """Start the device."""
        if self.state == STATE_PAUSED:
            self._device.resume()
        else:
            self._device.start()

    def set_fan_speed(self, fan_speed: str, **kwargs) -> None:
        """Set fan speed."""
        self._device.set_power_mode(EYE_POWER_MODE_STR_TO_ENUM[fan_speed])
