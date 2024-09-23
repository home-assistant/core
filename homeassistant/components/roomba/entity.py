"""Base class for iRobot devices."""

from __future__ import annotations

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
)
from homeassistant.const import ATTR_CONNECTIONS, STATE_IDLE, STATE_PAUSED
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from . import roomba_reported_state
from .const import DOMAIN

STATE_MAP = {
    "": STATE_IDLE,
    "charge": STATE_DOCKED,
    "evac": STATE_RETURNING,  # Emptying at cleanbase
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

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, roomba, blid):
        """Initialize the iRobot handler."""
        self.vacuum = roomba
        self._blid = blid
        self.vacuum_state = roomba_reported_state(roomba)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.robot_unique_id)},
            serial_number=self.vacuum_state.get("hwPartsRev", {}).get("navSerialNo"),
            manufacturer="iRobot",
            model=self.vacuum_state.get("sku"),
            name=str(self.vacuum_state.get("name")),
            sw_version=self.vacuum_state.get("softwareVer"),
            hw_version=self.vacuum_state.get("hardwareRev"),
        )

        if mac_address := self.vacuum_state.get("hwPartsRev", {}).get(
            "wlan0HwAddr", self.vacuum_state.get("mac")
        ):
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, mac_address)
            }

    @property
    def robot_unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return f"roomba_{self._blid}"

    @property
    def unique_id(self):
        """Return the uniqueid of the vacuum cleaner."""
        return self.robot_unique_id

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.vacuum_state.get("batPct")

    @property
    def run_stats(self):
        """Return the run stats."""
        return self.vacuum_state.get("bbrun", {})

    @property
    def mission_stats(self):
        """Return the mission stats."""
        return self.vacuum_state.get("bbmssn", {})

    @property
    def battery_stats(self):
        """Return the battery stats."""
        return self.vacuum_state.get("bbchg3", {})

    @property
    def last_mission(self):
        """Return last mission start time."""
        if (
            ts := self.vacuum_state.get("cleanMissionStatus", {}).get("mssnStrtTm")
        ) is None or ts == 0:
            return None
        return dt_util.utc_from_timestamp(ts)

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

    def new_state_filter(self, new_state):
        """Filter out wifi state messages."""
        return len(new_state) > 1 or "signal" not in new_state

    def on_message(self, json_data):
        """Update state on message change."""
        state = json_data.get("state", {}).get("reported", {})
        if self.new_state_filter(state):
            self.schedule_update_ha_state()
