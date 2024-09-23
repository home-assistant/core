"""Base class for iRobot devices."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    STATE_CLEANING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.const import STATE_PAUSED
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from ..entity import IRobotEntity

_LOGGER = logging.getLogger(__name__)

ATTR_CLEANING_TIME = "cleaning_time"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_ERROR = "error"
ATTR_ERROR_CODE = "error_code"
ATTR_POSITION = "position"
ATTR_SOFTWARE_VERSION = "software_version"

# Commonly supported features
SUPPORT_IROBOT = (
    VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STATE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.LOCATE
)


class IRobotVacuum(IRobotEntity, StateVacuumEntity):
    """Base class for iRobot robots."""

    _attr_name = None
    _attr_supported_features = SUPPORT_IROBOT
    _attr_available = True  # Always available, otherwise setup will fail

    def __init__(self, roomba, blid):
        """Initialize the iRobot handler."""
        super().__init__(roomba, blid)
        self._cap_position = self.vacuum_state.get("cap", {}).get("pose") == 1

    @property
    def state(self):
        """Return the state of the vacuum cleaner."""
        return self._robot_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        state = self.vacuum_state

        # Roomba software version
        software_version = state.get("softwareVer")

        # Set properties that are to appear in the GUI
        state_attrs = {ATTR_SOFTWARE_VERSION: software_version}

        # Set legacy status to avoid break changes
        state_attrs[ATTR_STATUS] = self.vacuum.current_state

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self.state == STATE_CLEANING:
            # Get clean mission status
            (
                state_attrs[ATTR_CLEANING_TIME],
                state_attrs[ATTR_CLEANED_AREA],
            ) = self.get_cleaning_status(state)

        # Error
        if self.vacuum.error_code != 0:
            state_attrs[ATTR_ERROR] = self.vacuum.error_message
            state_attrs[ATTR_ERROR_CODE] = self.vacuum.error_code

        # Not all Roombas expose position data
        # https://github.com/koalazak/dorita980/issues/48
        if self._cap_position:
            pos_state = state.get("pose", {})
            position = None
            pos_x = pos_state.get("point", {}).get("x")
            pos_y = pos_state.get("point", {}).get("y")
            theta = pos_state.get("theta")
            if all(item is not None for item in (pos_x, pos_y, theta)):
                position = f"({pos_x}, {pos_y}, {theta})"
            state_attrs[ATTR_POSITION] = position

        return state_attrs

    def get_cleaning_status(self, state) -> tuple[int, int]:
        """Return the cleaning time and cleaned area from the device."""
        if not (mission_state := state.get("cleanMissionStatus")):
            return (0, 0)

        if cleaning_time := mission_state.get("mssnM", 0):
            pass
        elif start_time := mission_state.get("mssnStrtTm"):
            now = dt_util.as_timestamp(dt_util.utcnow())
            if now > start_time:
                cleaning_time = (now - start_time) // 60

        if cleaned_area := mission_state.get("sqft", 0):  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if self.hass.config.units is METRIC_SYSTEM:
                cleaned_area = round(cleaned_area * 0.0929)

        return (cleaning_time, cleaned_area)

    def on_message(self, json_data):
        """Update state on message change."""
        state = json_data.get("state", {}).get("reported", {})
        if self.new_state_filter(state):
            _LOGGER.debug("Got new state from the vacuum: %s", json_data)
            self.schedule_update_ha_state()

    async def async_start(self):
        """Start or resume the cleaning task."""
        if self.state == STATE_PAUSED:
            await self.hass.async_add_executor_job(self.vacuum.send_command, "resume")
        else:
            await self.hass.async_add_executor_job(self.vacuum.send_command, "start")

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "stop")

    async def async_pause(self):
        """Pause the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "pause")

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        if self.state == STATE_CLEANING:
            await self.async_pause()
            for _ in range(10):
                if self.state == STATE_PAUSED:
                    break
                await asyncio.sleep(1)
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
