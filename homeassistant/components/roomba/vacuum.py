"""Support for Wi-Fi enabled iRobot Roombas."""
import json
import logging

from homeassistant.components.vacuum import (
    SUPPORT_BATTERY,
    SUPPORT_FAN_SPEED,
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
from .const import BLID, DOMAIN, ROOMBA_SESSION

_LOGGER = logging.getLogger(__name__)

ATTR_BIN_FULL = "bin_full"
ATTR_BIN_PRESENT = "bin_present"
ATTR_CLEANING_TIME = "cleaning_time"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_ERROR = "error"
ATTR_POSITION = "position"
ATTR_SOFTWARE_VERSION = "software_version"
ATTR_DETECTED_PAD = "detected_pad"
ATTR_LID_CLOSED = "lid_closed"
ATTR_TANK_PRESENT = "tank_present"
ATTR_TANK_LEVEL = "tank_level"
ATTR_PAD_WETNESS = "spray_amount"

FAN_SPEED_AUTOMATIC = "Automatic"
FAN_SPEED_ECO = "Eco"
FAN_SPEED_PERFORMANCE = "Performance"
FAN_SPEEDS = [FAN_SPEED_AUTOMATIC, FAN_SPEED_ECO, FAN_SPEED_PERFORMANCE]

OVERLAP_STANDARD = 67
OVERLAP_DEEP = 85
OVERLAP_EXTENDED = 25
MOP_STANDARD = "Standard"
MOP_DEEP = "Deep"
MOP_EXTENDED = "Extended"
BRAAVA_MOP_BEHAVIORS = [MOP_STANDARD, MOP_DEEP, MOP_EXTENDED]
BRAAVA_SPRAY_AMOUNT = [1, 2, 3]

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

# Only Roombas with CarpetBost can set their fanspeed
SUPPORT_ROOMBA_CARPET_BOOST = SUPPORT_IROBOT | SUPPORT_FAN_SPEED

# Braava Jets can set mopping behavior through fanspeed
SUPPORT_BRAAVA = SUPPORT_IROBOT | SUPPORT_FAN_SPEED


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]

    # Get the capabilities of our unit
    state = roomba_reported_state(roomba)
    capabilities = state.get("cap", {})
    cap_carpet_boost = capabilities.get("carpetBoost")
    detected_pad = state.get("detectedPad")
    if detected_pad is not None:
        constructor = BraavaJet
    elif cap_carpet_boost == 1:
        constructor = RoombaVacuumCarpetBoost
    else:
        constructor = RoombaVacuum

    roomba_vac = constructor(roomba, blid)
    async_add_entities([roomba_vac], True)


class IRobotBase(VacuumDevice):
    """Base class for iRobot robots."""

    def __init__(self, roomba, blid):
        """Initialize the Roomba handler."""
        self._available = False
        self._battery_level = None
        self._fan_speed = None
        self._is_on = False
        self._state_attrs = {}
        self._status = None
        self.vacuum = roomba
        self.vacuum_state = roomba_reported_state(roomba)
        self._blid = blid
        self._name = self.vacuum_state.get("name")
        self._version = self.vacuum_state.get("softwareVer")
        self._sku = self.vacuum_state.get("sku")
        self._cap_position = self.vacuum_state.get("cap", {}).get("pose") == 1

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
        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return []

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self._status

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "start")
        self._is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        await self.async_stop()
        await self.async_return_to_base()

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "stop")
        self._is_on = False

    async def async_resume(self, **kwargs):
        """Resume the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "resume")
        self._is_on = True

    async def async_pause(self):
        """Pause the cleaning cycle."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "pause")
        self._is_on = False

    async def async_start_pause(self, **kwargs):
        """Pause the cleaning task or resume it."""
        if self.vacuum_state and self.is_on:  # vacuum is running
            await self.async_pause()
        elif self._status == "Stopped":  # vacuum is stopped
            await self.async_resume()
        else:  # vacuum is off
            await self.async_turn_on()

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self.hass.async_add_executor_job(self.vacuum.send_command, "dock")
        self._is_on = False

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

    async def async_update(self):
        """Fetch state from the device."""
        state = self.vacuum.master_state.get("state", {}).get("reported", {})
        _LOGGER.debug("Got new state from the vacuum: %s", state)
        self.vacuum_state = state
        self._available = True

        # Roomba software version
        software_version = state.get("softwareVer")

        # Error message in plain english
        error_msg = "None"
        if hasattr(self.vacuum, "error_message"):
            error_msg = self.vacuum.error_message

        self._battery_level = state.get("batPct")
        self._status = self.vacuum.current_state
        self._is_on = self._status in ["Running"]

        # Set properties that are to appear in the GUI
        self._state_attrs = {ATTR_SOFTWARE_VERSION: software_version}

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self._is_on:
            # Get clean mission status
            mission_state = state.get("cleanMissionStatus", {})
            cleaning_time = mission_state.get("mssnM")
            cleaned_area = mission_state.get("sqft")  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if cleaned_area and self.hass.config.units.is_metric:
                cleaned_area = round(cleaned_area * 0.0929)
            self._state_attrs[ATTR_CLEANING_TIME] = cleaning_time
            self._state_attrs[ATTR_CLEANED_AREA] = cleaned_area

        # Skip error attr if there is none
        if error_msg and error_msg != "None":
            self._state_attrs[ATTR_ERROR] = error_msg

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
            self._state_attrs[ATTR_POSITION] = position


class RoombaVacuum(IRobotBase):
    """Basic Roomba robot (without carpet boost)."""

    async def async_update(self):
        """Fetch state from the device."""
        await super().async_update()

        # Get bin state
        bin_state = self._get_bin_state(self.vacuum_state)
        self._state_attrs.update(bin_state)

    @staticmethod
    def _get_bin_state(state):
        bin_raw_state = state.get("bin", {})
        bin_state = {}
        if bin_raw_state.get("present") is not None:
            bin_state[ATTR_BIN_PRESENT] = bin_raw_state.get("present")

        if bin_raw_state.get("full") is not None:
            bin_state[ATTR_BIN_FULL] = bin_raw_state.get("full")
        return bin_state


class RoombaVacuumCarpetBoost(RoombaVacuum):
    """Roomba robot with carpet boost."""

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ROOMBA_CARPET_BOOST

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return FAN_SPEEDS

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
            self._fan_speed = FAN_SPEED_AUTOMATIC
        elif fan_speed == FAN_SPEED_ECO:
            high_perf = False
            carpet_boost = False
            self._fan_speed = FAN_SPEED_ECO
        elif fan_speed == FAN_SPEED_PERFORMANCE:
            high_perf = True
            carpet_boost = False
            self._fan_speed = FAN_SPEED_PERFORMANCE
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

    async def async_update(self):
        """Fetch state from the device."""
        await super().async_update()

        # Fan speed mode (Performance, Automatic or Eco)
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
        self._fan_speed = fan_speed


class BraavaJet(IRobotBase):
    """Braava Jet."""

    def __init__(self, roomba, blid):
        """Initialize the Roomba handler."""
        super().__init__(roomba, blid)

        # Initialize fan speed list
        speed_list = []
        for behavior in BRAAVA_MOP_BEHAVIORS:
            for spray in BRAAVA_SPRAY_AMOUNT:
                speed_list.append(f"{behavior}-{spray}")
        self._speed_list = speed_list

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_BRAAVA

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        behavior, spray = self._fan_speed
        return f"{behavior}-{spray}"

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return self._speed_list

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
            self.vacuum.client.publish,
            "delta",
            json.dumps(
                {
                    "rankOverlap": overlap,
                    "padWetness": {"disposable": spray, "reusable": spray},
                }
            ),
        )

    async def async_update(self):
        """Fetch state from the device."""
        await super().async_update()

        # Get Braava state
        state = self.vacuum_state
        detected_pad = state.get("detectedPad")
        mop_ready = state.get("mopReady", {})
        lid_closed = mop_ready.get("lidClosed")
        tank_present = mop_ready.get("tankPresent")
        tank_level = state.get("tankLvl")
        self._state_attrs[ATTR_DETECTED_PAD] = detected_pad
        self._state_attrs[ATTR_LID_CLOSED] = lid_closed
        self._state_attrs[ATTR_TANK_PRESENT] = tank_present
        self._state_attrs[ATTR_TANK_LEVEL] = tank_level

        # Mopping behavior and spray amount as fan speed
        rank_overlap = state.get("rankOverlap", {})
        behavior = None
        if rank_overlap == OVERLAP_STANDARD:
            behavior = MOP_STANDARD
        elif rank_overlap == OVERLAP_DEEP:
            behavior = MOP_DEEP
        elif rank_overlap == OVERLAP_EXTENDED:
            behavior = MOP_EXTENDED
        pad_wetness = state.get("padWetness", {})
        # "disposable" and "reusable" values are always the same
        pad_wetness_value = pad_wetness.get("disposable")
        self._fan_speed = (behavior, pad_wetness_value)
