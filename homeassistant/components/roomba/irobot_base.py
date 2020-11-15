"""Base class for iRobot devices."""
import asyncio
import logging

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    StateVacuumEntity,
)
from homeassistant.helpers.entity import Entity

from . import roomba_reported_state
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_CLEANING_TIME = "cleaning_time"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_ERROR = "error"
ATTR_ERROR_CODE = "error_code"
ATTR_POSITION = "position"
ATTR_SOFTWARE_VERSION = "software_version"

# Commonly supported features
SUPPORT_IROBOT = (
    SUPPORT_BATTERY
    | SUPPORT_PAUSE
    | SUPPORT_RETURN_HOME
    | SUPPORT_SEND_COMMAND
    | SUPPORT_START
    | SUPPORT_STATE
    | SUPPORT_STATUS
    | SUPPORT_STOP
    | SUPPORT_LOCATE
)

STATE_MAP = {
    "": STATE_IDLE,
    "charge": STATE_DOCKED,
    "hmMidMsn": STATE_CLEANING,  # Recharging at the middle of a cycle
    "hmPostMsn": STATE_RETURNING,  # Cycle finished
    "hmUsrDock": STATE_RETURNING,
    "pause": STATE_PAUSED,
    "run": STATE_CLEANING,
    "stop": STATE_IDLE,
    "stuck": STATE_ERROR,
}


class IRobotEntity(Entity):
    """Base class for iRobot Entities."""

    def __init__(self, roomba, blid):
        """Initialize the iRobot handler."""
        self.vacuum = roomba
        self._blid = blid
        self.vacuum_state = roomba_reported_state(roomba)
        self._name = self.vacuum_state.get("name")
        self._version = self.vacuum_state.get("softwareVer")
        self._sku = self.vacuum_state.get("sku")

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def robot_unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return f"roomba_{self._blid}"

    @property
    def unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return self.robot_unique_id

    @property
    def device_info(self):
        """Return the device info of the vacuum cleaner."""
        return {
            "identifiers": {(DOMAIN, self.robot_unique_id)},
            "manufacturer": "iRobot",
            "name": str(self._name),
            "sw_version": self._version,
            "model": self._sku,
        }

    @property
    def _battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.vacuum_state.get("batPct")

    @property
    def _robot_state(self):
        """Return the state of the vacuum cleaner."""
        clean_mission_status = self.vacuum_state.get("cleanMissionStatus", {})
        cycle = clean_mission_status.get("cycle")
        phase = clean_mission_status.get("phase")
        try:
            state = STATE_MAP[phase]
        except KeyError:
            return STATE_ERROR
        if cycle != "none" and state in (STATE_IDLE, STATE_DOCKED):
            state = STATE_PAUSED
        return state

    async def async_added_to_hass(self):
        """Register callback function."""
        self.vacuum.register_on_message_callback(self.on_message)

    def new_state_filter(self, new_state):  # pylint: disable=no-self-use
        """Filter out wifi state messages."""
        return len(new_state) > 1 or "signal" not in new_state

    def on_message(self, json_data):
        """Update state on message change."""
        state = json_data.get("state", {}).get("reported", {})
        if self.new_state_filter(state):
            self.schedule_update_ha_state()


class IRobotVacuum(IRobotEntity, StateVacuumEntity):
    """Base class for iRobot robots."""

    def __init__(self, roomba, blid):
        """Initialize the iRobot handler."""
        super().__init__(roomba, blid)
        self._cap_position = self.vacuum_state.get("cap", {}).get("pose") == 1

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_IROBOT

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def state(self):
        """Return the state of the vacuum cleaner."""
        return self._robot_state

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

        # Set properties that are to appear in the GUI
        state_attrs = {ATTR_SOFTWARE_VERSION: software_version}

        # Set legacy status to avoid break changes
        state_attrs[ATTR_STATUS] = self.vacuum.current_state

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self.state == STATE_CLEANING:
            # Get clean mission status
            mission_state = state.get("cleanMissionStatus", {})
            cleaning_time = mission_state.get("mssnM")
            cleaned_area = mission_state.get("sqft")  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if cleaned_area and self.hass.config.units.is_metric:
                cleaned_area = round(cleaned_area * 0.0929)
            state_attrs[ATTR_CLEANING_TIME] = cleaning_time
            state_attrs[ATTR_CLEANED_AREA] = cleaned_area

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
            if all(item is not None for item in [pos_x, pos_y, theta]):
                position = f"({pos_x}, {pos_y}, {theta})"
            state_attrs[ATTR_POSITION] = position

        return state_attrs

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
            for _ in range(0, 10):
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
