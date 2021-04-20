"""Shark IQ Wrapper."""
from __future__ import annotations

from collections.abc import Iterable
import logging

from sharkiqpy import OperatingModes, PowerModes, Properties, SharkIqVacuum

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    StateVacuumEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SHARK
from .update_coordinator import SharkIqUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Supported features
SUPPORT_SHARKIQ = (
    SUPPORT_BATTERY
    | SUPPORT_FAN_SPEED
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_START
    | SUPPORT_STATE
    | SUPPORT_STATUS
    | SUPPORT_STOP
    | SUPPORT_LOCATE
)

OPERATING_STATE_MAP = {
    OperatingModes.PAUSE: STATE_PAUSED,
    OperatingModes.START: STATE_CLEANING,
    OperatingModes.STOP: STATE_IDLE,
    OperatingModes.RETURN: STATE_RETURNING,
}

FAN_SPEEDS_MAP = {
    "Eco": PowerModes.ECO,
    "Normal": PowerModes.NORMAL,
    "Max": PowerModes.MAX,
}

STATE_RECHARGING_TO_RESUME = "recharging_to_resume"

# Attributes to expose
ATTR_ERROR_CODE = "last_error_code"
ATTR_ERROR_MSG = "last_error_message"
ATTR_LOW_LIGHT = "low_light"
ATTR_RECHARGE_RESUME = "recharge_and_resume"
ATTR_RSSI = "rssi"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Shark IQ vacuum cleaner."""
    coordinator: SharkIqUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    devices: Iterable[SharkIqVacuum] = coordinator.shark_vacs.values()
    device_names = [d.name for d in devices]
    _LOGGER.debug(
        "Found %d Shark IQ device(s): %s",
        len(device_names),
        ", ".join([d.name for d in devices]),
    )
    async_add_entities([SharkVacuumEntity(d, coordinator) for d in devices])


class SharkVacuumEntity(CoordinatorEntity, StateVacuumEntity):
    """Shark IQ vacuum entity."""

    def __init__(self, sharkiq: SharkIqVacuum, coordinator: SharkIqUpdateCoordinator):
        """Create a new SharkVacuumEntity."""
        super().__init__(coordinator)
        self.sharkiq = sharkiq

    def clean_spot(self, **kwargs):
        """Clean a spot. Not yet implemented."""
        raise NotImplementedError()

    def send_command(self, command, params=None, **kwargs):
        """Send a command to the vacuum. Not yet implemented."""
        raise NotImplementedError()

    @property
    def is_online(self) -> bool:
        """Tell us if the device is online."""
        return self.coordinator.device_is_online(self.sharkiq.serial_number)

    @property
    def name(self) -> str:
        """Device name."""
        return self.sharkiq.name

    @property
    def serial_number(self) -> str:
        """Vacuum API serial number (DSN)."""
        return self.sharkiq.serial_number

    @property
    def model(self) -> str:
        """Vacuum model number."""
        if self.sharkiq.vac_model_number:
            return self.sharkiq.vac_model_number
        return self.sharkiq.oem_model_number

    @property
    def device_info(self) -> dict:
        """Device info dictionary."""
        return {
            "identifiers": {(DOMAIN, self.serial_number)},
            "name": self.name,
            "manufacturer": SHARK,
            "model": self.model,
            "sw_version": self.sharkiq.get_property_value(
                Properties.ROBOT_FIRMWARE_VERSION
            ),
        }

    @property
    def supported_features(self) -> int:
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_SHARKIQ

    @property
    def is_docked(self) -> bool | None:
        """Is vacuum docked."""
        return self.sharkiq.get_property_value(Properties.DOCKED_STATUS)

    @property
    def error_code(self) -> int | None:
        """Return the last observed error code (or None)."""
        return self.sharkiq.error_code

    @property
    def error_message(self) -> str | None:
        """Return the last observed error message (or None)."""
        if not self.error_code:
            return None
        return self.sharkiq.error_text

    @property
    def operating_mode(self) -> str | None:
        """Operating mode.."""
        op_mode = self.sharkiq.get_property_value(Properties.OPERATING_MODE)
        return OPERATING_STATE_MAP.get(op_mode)

    @property
    def recharging_to_resume(self) -> int | None:
        """Return True if vacuum set to recharge and resume cleaning."""
        return self.sharkiq.get_property_value(Properties.RECHARGING_TO_RESUME)

    @property
    def state(self):
        """
        Get the current vacuum state.

        NB: Currently, we do not return an error state because they can be very, very stale.
        In the app, these are (usually) handled by showing the robot as stopped and sending the
        user a notification.
        """
        if self.is_docked:
            return STATE_DOCKED
        return self.operating_mode

    @property
    def unique_id(self) -> str:
        """Return the unique id of the vacuum cleaner."""
        return self.serial_number

    @property
    def available(self) -> bool:
        """Determine if the sensor is available based on API results."""
        # If the last update was successful...
        return self.coordinator.last_update_success and self.is_online

    @property
    def battery_level(self):
        """Get the current battery level."""
        return self.sharkiq.get_property_value(Properties.BATTERY_CAPACITY)

    async def async_return_to_base(self, **kwargs):
        """Have the device return to base."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.RETURN)
        await self.coordinator.async_refresh()

    async def async_pause(self):
        """Pause the cleaning task."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.PAUSE)
        await self.coordinator.async_refresh()

    async def async_start(self):
        """Start the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.START)
        await self.coordinator.async_refresh()

    async def async_stop(self, **kwargs):
        """Stop the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.STOP)
        await self.coordinator.async_refresh()

    async def async_locate(self, **kwargs):
        """Cause the device to generate a loud chirp."""
        await self.sharkiq.async_find_device()

    @property
    def fan_speed(self) -> str:
        """Return the current fan speed."""
        fan_speed = None
        speed_level = self.sharkiq.get_property_value(Properties.POWER_MODE)
        for k, val in FAN_SPEEDS_MAP.items():
            if val == speed_level:
                fan_speed = k
        return fan_speed

    async def async_set_fan_speed(self, fan_speed: str, **kwargs):
        """Set the fan speed."""
        await self.sharkiq.async_set_property_value(
            Properties.POWER_MODE, FAN_SPEEDS_MAP.get(fan_speed.capitalize())
        )
        await self.coordinator.async_refresh()

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEEDS_MAP)

    # Various attributes we want to expose
    @property
    def recharge_resume(self) -> bool | None:
        """Recharge and resume mode active."""
        return self.sharkiq.get_property_value(Properties.RECHARGE_RESUME)

    @property
    def rssi(self) -> int | None:
        """Get the WiFi RSSI."""
        return self.sharkiq.get_property_value(Properties.RSSI)

    @property
    def low_light(self):
        """Let us know if the robot is operating in low-light mode."""
        return self.sharkiq.get_property_value(Properties.LOW_LIGHT_MISSION)

    @property
    def extra_state_attributes(self) -> dict:
        """Return a dictionary of device state attributes specific to sharkiq."""
        data = {
            ATTR_ERROR_CODE: self.error_code,
            ATTR_ERROR_MSG: self.sharkiq.error_text,
            ATTR_LOW_LIGHT: self.low_light,
            ATTR_RECHARGE_RESUME: self.recharge_resume,
        }
        return data
