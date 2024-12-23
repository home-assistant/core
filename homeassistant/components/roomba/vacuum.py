"""Support for Wi-Fi enabled iRobot Roombas."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import roomba_reported_state
from .const import DOMAIN
from .entity import IRobotEntity
from .models import RoombaData

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

STATE_MAP = {
    "": VacuumActivity.IDLE,
    "charge": VacuumActivity.DOCKED,
    "evac": VacuumActivity.RETURNING,  # Emptying at cleanbase
    "hmMidMsn": VacuumActivity.CLEANING,  # Recharging at the middle of a cycle
    "hmPostMsn": VacuumActivity.RETURNING,  # Cycle finished
    "hmUsrDock": VacuumActivity.RETURNING,
    "pause": VacuumActivity.PAUSED,
    "run": VacuumActivity.CLEANING,
    "stop": VacuumActivity.IDLE,
    "stuck": VacuumActivity.ERROR,
}

_LOGGER = logging.getLogger(__name__)
ATTR_SOFTWARE_VERSION = "software_version"
ATTR_CLEANING_TIME = "cleaning_time"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_ERROR = "error"
ATTR_ERROR_CODE = "error_code"
ATTR_POSITION = "position"
ATTR_SOFTWARE_VERSION = "software_version"

ATTR_BIN_FULL = "bin_full"
ATTR_BIN_PRESENT = "bin_present"

FAN_SPEED_AUTOMATIC = "Automatic"
FAN_SPEED_ECO = "Eco"
FAN_SPEED_PERFORMANCE = "Performance"
FAN_SPEEDS = [FAN_SPEED_AUTOMATIC, FAN_SPEED_ECO, FAN_SPEED_PERFORMANCE]

# Only Roombas with CarpetBost can set their fanspeed
SUPPORT_ROOMBA_CARPET_BOOST = SUPPORT_IROBOT | VacuumEntityFeature.FAN_SPEED

ATTR_DETECTED_PAD = "detected_pad"
ATTR_LID_CLOSED = "lid_closed"
ATTR_TANK_PRESENT = "tank_present"
ATTR_TANK_LEVEL = "tank_level"
ATTR_PAD_WETNESS = "spray_amount"

OVERLAP_STANDARD = 67
OVERLAP_DEEP = 85
OVERLAP_EXTENDED = 25
MOP_STANDARD = "Standard"
MOP_DEEP = "Deep"
MOP_EXTENDED = "Extended"
BRAAVA_MOP_BEHAVIORS = [MOP_STANDARD, MOP_DEEP, MOP_EXTENDED]
BRAAVA_SPRAY_AMOUNT = [1, 2, 3]

# Braava Jets can set mopping behavior through fanspeed
SUPPORT_BRAAVA = SUPPORT_IROBOT | VacuumEntityFeature.FAN_SPEED


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data: RoombaData = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data.roomba
    blid = domain_data.blid

    # Get the capabilities of our unit
    state = roomba_reported_state(roomba)
    capabilities = state.get("cap", {})
    cap_carpet_boost = capabilities.get("carpetBoost")
    detected_pad = state.get("detectedPad")
    constructor: type[IRobotVacuum]
    if detected_pad is not None:
        constructor = BraavaJet
    elif cap_carpet_boost == 1:
        constructor = RoombaVacuumCarpetBoost
    else:
        constructor = RoombaVacuum

    roomba_vac = constructor(roomba, blid)
    async_add_entities([roomba_vac])


class IRobotVacuum(IRobotEntity, StateVacuumEntity):
    """Base class for iRobot robots."""

    _attr_name = None
    _attr_supported_features = SUPPORT_IROBOT
    _attr_available = True  # Always available, otherwise setup will fail

    def __init__(self, roomba, blid) -> None:
        """Initialize the iRobot handler."""
        super().__init__(roomba, blid)
        self._cap_position = self.vacuum_state.get("cap", {}).get("pose") == 1

    @property
    def activity(self):
        """Return the state of the vacuum cleaner."""
        clean_mission_status = self.vacuum_state.get("cleanMissionStatus", {})
        cycle = clean_mission_status.get("cycle")
        phase = clean_mission_status.get("phase")
        try:
            state = STATE_MAP[phase]
        except KeyError:
            return VacuumActivity.ERROR
        if cycle != "none" and state in (VacuumActivity.IDLE, VacuumActivity.DOCKED):
            state = VacuumActivity.PAUSED
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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
        if self.state == VacuumActivity.CLEANING:
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

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        if self.state == VacuumActivity.PAUSED:
            await self.hass.async_add_executor_job(self.vacuum.send_command, "resume")
        else:
            await self.hass.async_add_executor_job(self.vacuum.send_command, "start")

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "stop")

    async def async_pause(self) -> None:
        """Pause the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "pause")

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        if self.state == VacuumActivity.CLEANING:
            await self.async_pause()
            for _ in range(10):
                if self.state == VacuumActivity.PAUSED:
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


class RoombaVacuum(IRobotVacuum):
    """Basic Roomba robot (without carpet boost)."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        state_attrs = super().extra_state_attributes

        # Get bin state
        bin_raw_state = self.vacuum_state.get("bin", {})
        bin_state = {}
        if bin_raw_state.get("present") is not None:
            bin_state[ATTR_BIN_PRESENT] = bin_raw_state.get("present")
        if bin_raw_state.get("full") is not None:
            bin_state[ATTR_BIN_FULL] = bin_raw_state.get("full")
        state_attrs.update(bin_state)

        return state_attrs


class RoombaVacuumCarpetBoost(RoombaVacuum):
    """Roomba robot with carpet boost."""

    _attr_fan_speed_list = FAN_SPEEDS
    _attr_supported_features = SUPPORT_ROOMBA_CARPET_BOOST

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        fan_speed = None
        carpet_boost = self.vacuum_state.get("carpetBoost")
        high_perf = self.vacuum_state.get("vacHigh")
        if carpet_boost is not None and high_perf is not None:
            if carpet_boost:
                fan_speed = FAN_SPEED_AUTOMATIC
            elif high_perf:
                fan_speed = FAN_SPEED_PERFORMANCE
            else:  # carpet_boost and high_perf are False
                fan_speed = FAN_SPEED_ECO
        return fan_speed

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            fan_speed = fan_speed.capitalize()
        _LOGGER.debug("Set fan speed to: %s", fan_speed)
        high_perf = None
        carpet_boost = None
        if fan_speed == FAN_SPEED_AUTOMATIC:
            high_perf = False
            carpet_boost = True
        elif fan_speed == FAN_SPEED_ECO:
            high_perf = False
            carpet_boost = False
        elif fan_speed == FAN_SPEED_PERFORMANCE:
            high_perf = True
            carpet_boost = False
        else:
            _LOGGER.error("No such fan speed available: %s", fan_speed)
            return
        # The set_preference method does only accept string values
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "carpetBoost", str(carpet_boost)
        )
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "vacHigh", str(high_perf)
        )


class BraavaJet(IRobotVacuum):
    """Braava Jet."""

    _attr_supported_features = SUPPORT_BRAAVA

    def __init__(self, roomba, blid) -> None:
        """Initialize the Roomba handler."""
        super().__init__(roomba, blid)

        # Initialize fan speed list
        self._attr_fan_speed_list = [
            f"{behavior}-{spray}"
            for behavior in BRAAVA_MOP_BEHAVIORS
            for spray in BRAAVA_SPRAY_AMOUNT
        ]

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        # Mopping behavior and spray amount as fan speed
        rank_overlap = self.vacuum_state.get("rankOverlap", {})
        behavior = None
        if rank_overlap == OVERLAP_STANDARD:
            behavior = MOP_STANDARD
        elif rank_overlap == OVERLAP_DEEP:
            behavior = MOP_DEEP
        elif rank_overlap == OVERLAP_EXTENDED:
            behavior = MOP_EXTENDED
        pad_wetness = self.vacuum_state.get("padWetness", {})
        # "disposable" and "reusable" values are always the same
        pad_wetness_value = pad_wetness.get("disposable")
        return f"{behavior}-{pad_wetness_value}"

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        try:
            split = fan_speed.split("-", 1)
            behavior = split[0]
            spray = int(split[1])
            if behavior.capitalize() in BRAAVA_MOP_BEHAVIORS:
                behavior = behavior.capitalize()
        except IndexError:
            _LOGGER.error(
                "Fan speed error: expected {behavior}-{spray_amount}, got '%s'",
                fan_speed,
            )
            return
        except ValueError:
            _LOGGER.error("Spray amount error: expected integer, got '%s'", split[1])
            return
        if behavior not in BRAAVA_MOP_BEHAVIORS:
            _LOGGER.error(
                "Mop behavior error: expected one of %s, got '%s'",
                str(BRAAVA_MOP_BEHAVIORS),
                behavior,
            )
            return
        if spray not in BRAAVA_SPRAY_AMOUNT:
            _LOGGER.error(
                "Spray amount error: expected one of %s, got '%d'",
                str(BRAAVA_SPRAY_AMOUNT),
                spray,
            )
            return

        overlap = 0
        if behavior == MOP_STANDARD:
            overlap = OVERLAP_STANDARD
        elif behavior == MOP_DEEP:
            overlap = OVERLAP_DEEP
        else:
            overlap = OVERLAP_EXTENDED
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference, "rankOverlap", overlap
        )
        await self.hass.async_add_executor_job(
            self.vacuum.set_preference,
            "padWetness",
            {"disposable": spray, "reusable": spray},
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        state_attrs = super().extra_state_attributes

        # Get Braava state
        state = self.vacuum_state
        detected_pad = state.get("detectedPad")
        mop_ready = state.get("mopReady", {})
        lid_closed = mop_ready.get("lidClosed")
        tank_present = mop_ready.get("tankPresent")
        tank_level = state.get("tankLvl")
        state_attrs[ATTR_DETECTED_PAD] = detected_pad
        state_attrs[ATTR_LID_CLOSED] = lid_closed
        state_attrs[ATTR_TANK_PRESENT] = tank_present
        state_attrs[ATTR_TANK_LEVEL] = tank_level

        return state_attrs
