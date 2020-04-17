"""Base class for iRobot devices."""
import logging

from homeassistant.components.vacuum import (
    SUPPORT_BATTERY,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumDevice,
)

from . import roomba_reported_state
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLEANING_TIME = "cleaning_time"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_ERROR = "error"
ATTR_POSITION = "position"
ATTR_SOFTWARE_VERSION = "software_version"

# Commonly supported features
SUPPORT_IROBOT = (
    SUPPORT_BATTERY
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_SEND_COMMAND
    | SUPPORT_STATUS
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_LOCATE
)


class IRobotBase(VacuumDevice):
    """Base class for iRobot robots."""

    def __init__(self, roomba, blid):
        """Initialize the Roomba handler."""
        self.vacuum = roomba
        self.vacuum_state = roomba_reported_state(roomba)
        self._blid = blid
        self._name = self.vacuum_state.get("name")
        self._version = self.vacuum_state.get("softwareVer")
        self._sku = self.vacuum_state.get("sku")
        self._cap_position = self.vacuum_state.get("cap", {}).get("pose") == 1

        # Register callback function
        self.vacuum.register_on_message_callback(self.on_message)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return f"roomba_{self._blid}"

    @property
    def device_info(self):
        """Return the device info of the vacuum cleaner."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": "iRobot",
            "name": str(self._name),
            "sw_version": self._version,
            "model": self._sku,
        }

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_IROBOT

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return None

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return []

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.vacuum_state.get("batPct")

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self.vacuum.current_state

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.status == "Running"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Always available, otherwise setup will fail

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        state = self.vacuum_state

        # Roomba software version
        software_version = state.get("softwareVer")

        # Error message in plain english
        error_msg = "None"
        if hasattr(self.vacuum, "error_message"):
            error_msg = self.vacuum.error_message

        # Set properties that are to appear in the GUI
        state_attrs = {ATTR_SOFTWARE_VERSION: software_version}

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self.is_on:
            # Get clean mission status
            mission_state = state.get("cleanMissionStatus", {})
            cleaning_time = mission_state.get("mssnM")
            cleaned_area = mission_state.get("sqft")  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if cleaned_area and self.hass.config.units.is_metric:
                cleaned_area = round(cleaned_area * 0.0929)
            state_attrs[ATTR_CLEANING_TIME] = cleaning_time
            state_attrs[ATTR_CLEANED_AREA] = cleaned_area

        # Skip error attr if there is none
        if error_msg and error_msg != "None":
            state_attrs[ATTR_ERROR] = error_msg

        # Not all Roombas expose position data
        # https://github.com/koalazak/dorita980/issues/48
        if self._cap_position:
            pos_state = state.get("pose", {})
            position = None
            pos_x = pos_state.get("point", {}).get("x")
            pos_y = pos_state.get("point", {}).get("y")
            theta = pos_state.get("theta")
            if all(item is not None for item in [pos_x, pos_y, theta]):
                position = f"({pos_x}, {pos_y}, {theta})"
            state_attrs[ATTR_POSITION] = position

        return state_attrs

    def on_message(self, json_data):
        """Update state on message change."""
        _LOGGER.debug("Got new state from the vacuum: %s", json_data)
        self.vacuum_state = self.vacuum.master_state.get("state", {}).get(
            "reported", {}
        )
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "start")

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        await self.async_stop()
        await self.async_return_to_base()

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "stop")

    async def async_resume(self, **kwargs):
        """Resume the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "resume")

    async def async_pause(self):
        """Pause the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "pause")

    async def async_start_pause(self, **kwargs):
        """Pause the cleaning task or resume it."""
        if self.vacuum_state and self.is_on:  # vacuum is running
            await self.async_pause()
        elif self.status == "Stopped":  # vacuum is stopped
            await self.async_resume()
        else:  # vacuum is off
            await self.async_turn_on()

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "dock")

    async def async_locate(self, **kwargs):
        """Located vacuum."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "find")

    async def async_send_command(self, command, params=None, **kwargs):
        """Send raw command."""
        _LOGGER.debug("async_send_command %s (%s), %s", command, params, kwargs)
        await self.hass.async_add_executor_job(
            self.vacuum.send_command, command, params
        )
        return True
