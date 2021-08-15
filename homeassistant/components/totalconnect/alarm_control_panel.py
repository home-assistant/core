"""Interfaces with TotalConnect alarm control panels."""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up TotalConnect alarm panels based on a config entry."""
    alarms = []

    coordinator = hass.data[DOMAIN][entry.entry_id]

    for location_id, location in coordinator.client.locations.items():
        location_name = location.location_name
        for partition_id in location.partitions.items():
            alarms.append(
                TotalConnectAlarm(
                    coordinator=coordinator,
                    name=location_name,
                    location_id=location_id,
                    partition_id=partition_id,
                )
            )

    async_add_entities(alarms, True)


class TotalConnectAlarm(CoordinatorEntity, alarm.AlarmControlPanelEntity):
    """Represent an TotalConnect status."""

    def __init__(self, coordinator, name, location_id, partition_id):
        """Initialize the TotalConnect status."""
        super().__init__(coordinator)
        self._client = coordinator.client
        self._location_id = location_id
        self._location = coordinator.client.locations[location_id]
        self._partition_id = partition_id
        self._partition = self._location.partitions[partition_id]
        self._state = None
        self._extra_state_attributes = {}

        """
        Set unique_id to location_id for partition 1 to avoid breaking change
        for most users with new support for partitions.
        Add _# for partition 2 and beyond.
        """
        if partition_id == 1:
            self._name = name
            self._unique_id = f"{location_id}"
        else:
            self._name = f"{name} partition {partition_id}"
            self._unique_id = f"{location_id}_{partition_id}"

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        attr = {
            "location_name": self._name,
            "location_id": self._location_id,
            "ac_loss": self._location.ac_loss,
            "low_battery": self._location.low_battery,
            "cover_tampered": self._location.is_cover_tampered(),
            "triggered_source": None,
            "triggered_zone": None,
        }

        if self._partition.is_disarmed():
            state = STATE_ALARM_DISARMED
        elif self._partition.is_armed_night():
            state = STATE_ALARM_ARMED_NIGHT
        elif self._partition.is_armed_home():
            state = STATE_ALARM_ARMED_HOME
        elif self._partition.is_armed_away():
            state = STATE_ALARM_ARMED_AWAY
        elif self._partition.is_armed_custom_bypass():
            state = STATE_ALARM_ARMED_CUSTOM_BYPASS
        elif self._partition.is_arming():
            state = STATE_ALARM_ARMING
        elif self._partition.is_disarming():
            state = STATE_ALARM_DISARMING
        elif self._partition.is_triggered_police():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Police/Medical"
        elif self._partition.is_triggered_fire():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Fire/Smoke"
        elif self._partition.is_triggered_gas():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Carbon Monoxide"
        else:
            logging.info("Total Connect Client returned unknown status")
            state = None

        self._state = state
        self._extra_state_attributes = attr

        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._extra_state_attributes

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if self._partition.disarm() is not True:
            raise HomeAssistantError(f"TotalConnect failed to disarm {self._name}.")

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if self._partition.arm_stay() is not True:
            raise HomeAssistantError(f"TotalConnect failed to arm home {self._name}.")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._partition.arm_away() is not True:
            raise HomeAssistantError(f"TotalConnect failed to arm away {self._name}.")

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        if self._partition.arm_stay_night() is not True:
            raise HomeAssistantError(f"TotalConnect failed to arm night {self._name}.")
