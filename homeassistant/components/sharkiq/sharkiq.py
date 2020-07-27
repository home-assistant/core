"""Shark IQ Wrapper."""


import logging
from typing import Dict, Optional

from sharkiqpy import OperatingModes, PowerModes, Properties, SharkIqVacuum

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
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

from .const import DOMAIN, SHARK

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
ATTR_RECHARGE_RESUME = "recharge_and_resume"
ATTR_RSSI = "rssi"


class SharkVacuumEntity(StateVacuumEntity):
    """Shark IQ vacuum entity."""

    def __init__(self, sharkiq: SharkIqVacuum):
        """Create a new SharkVacuumEntity."""
        self.sharkiq = sharkiq

    @property
    def should_poll(self):
        """Device updates via polling Ayla API."""
        return True

    def clean_spot(self, **kwargs):
        """Clean a spot. Not yet implemented."""
        raise NotImplementedError()

    def send_command(self, command, params=None, **kwargs):
        """Send a command to the vacuum. Not yet implemented."""
        raise NotImplementedError()

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
    def device_info(self) -> Dict:
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
    def is_docked(self) -> Optional[bool]:
        """Is vacuum docked."""
        return self.sharkiq.get_property_value(Properties.DOCKED_STATUS)

    @property
    def error_code(self) -> Optional[int]:
        """Error code or None."""
        # Errors remain for a while, so we should only show an error if the device is stopped
        if (
            self.sharkiq.get_property_value(Properties.OPERATING_MODE)
            == OperatingModes.STOP
            and not self.is_docked
        ):
            return self.sharkiq.get_property_value(Properties.ERROR_CODE)
        return None

    @property
    def operating_mode(self) -> Optional[str]:
        """Operating mode.."""
        op_mode = self.sharkiq.get_property_value(Properties.OPERATING_MODE)
        return OPERATING_STATE_MAP.get(op_mode)

    @property
    def recharging_to_resume(self) -> Optional[int]:
        """Return True if vacuum set to recharge and resume cleaning."""
        return self.sharkiq.get_property_value(Properties.RECHARGING_TO_RESUME)

    @property
    def state(self):
        """Get the current vacuum state."""
        if self.recharging_to_resume:
            return STATE_RECHARGING_TO_RESUME
        if self.is_docked:
            return STATE_DOCKED
        if self.error_code:
            return STATE_ERROR
        return self.operating_mode

    @property
    def unique_id(self) -> str:
        """Return the unique id of the vacuum cleaner."""
        return f"sharkiq-{self.serial_number:s}-vacuum"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Always available, otherwise setup will fail

    @property
    def battery_level(self):
        """Get the current battery level."""
        return self.sharkiq.get_property_value(Properties.BATTERY_CAPACITY)

    def update(self, property_list=None):
        """Update the known properties."""
        self.sharkiq.update(property_list)

    async def async_update(self, property_list=None):
        """Update the known properties asynchronously."""
        await self.sharkiq.async_update(property_list)

    def return_to_base(self, **kwargs):
        """Have the device return to base."""
        self.sharkiq.set_operating_mode(OperatingModes.RETURN)

    def pause(self):
        """Pause the cleaning task."""
        self.sharkiq.set_operating_mode(OperatingModes.PAUSE)

    def start(self):
        """Start the device."""
        self.sharkiq.set_operating_mode(OperatingModes.START)

    def stop(self, **kwargs):
        """Stop the device."""
        self.sharkiq.set_operating_mode(OperatingModes.STOP)

    def locate(self, **kwargs):
        """Cause the device to generate a loud chirp."""
        self.sharkiq.find_device()

    async def async_return_to_base(self, **kwargs):
        """Have the device return to base."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.RETURN)

    async def async_pause(self):
        """Pause the cleaning task."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.PAUSE)

    async def async_start(self):
        """Start the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.START)

    async def async_stop(self, **kwargs):
        """Stop the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.STOP)

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

    def set_fan_speed(self, fan_speed: str, **kwargs):
        """Set the fan speed."""
        self.sharkiq.set_property_value(
            Properties.POWER_MODE, FAN_SPEEDS_MAP.get(fan_speed.capitalize())
        )

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEEDS_MAP.keys())

    # Various attributes we want to expose
    @property
    def recharge_resume(self) -> Optional[bool]:
        """Recharge and resume mode active."""
        return self.sharkiq.get_property_value(Properties.RECHARGE_RESUME)

    @property
    def rssi(self) -> Optional[int]:
        """Get the WiFi RSSI."""
        return self.sharkiq.get_property_value(Properties.RSSI)

    @property
    def state_attributes(self) -> Dict:
        """Return a dictionary of device state attributes."""
        data = super().state_attributes
        data[ATTR_RSSI] = self.rssi
        data[ATTR_RECHARGE_RESUME] = self.recharge_resume
        return data
