"""Interfaces with TotalConnect alarm control panels."""
import logging

from total_connect_client import ArmingHelper
from total_connect_client.exceptions import BadResultCodeError

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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up TotalConnect alarm panels based on a config entry."""
    alarms = []

    coordinator = hass.data[DOMAIN][entry.entry_id]

    for location_id, location in coordinator.client.locations.items():
        location_name = location.location_name
        for partition_id in location.partitions:
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
        self._location_id = location_id
        self._location = coordinator.client.locations[location_id]
        self._partition_id = partition_id
        self._partition = self._location.partitions[partition_id]
        self._device = self._location.devices[self._location.security_device_id]
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
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.serial_number)},
            "name": self._device.name,
        }

    @property
    def state(self):
        """Return the state of the device."""
        attr = {
            "location_name": self._name,
            "location_id": self._location_id,
            "partition": self._partition_id,
            "ac_loss": self._location.ac_loss,
            "low_battery": self._location.low_battery,
            "cover_tampered": self._location.is_cover_tampered(),
            "triggered_source": None,
            "triggered_zone": None,
        }

        if self._partition.arming_state.is_disarmed():
            state = STATE_ALARM_DISARMED
        elif self._partition.arming_state.is_armed_night():
            state = STATE_ALARM_ARMED_NIGHT
        elif self._partition.arming_state.is_armed_home():
            state = STATE_ALARM_ARMED_HOME
        elif self._partition.arming_state.is_armed_away():
            state = STATE_ALARM_ARMED_AWAY
        elif self._partition.arming_state.is_armed_custom_bypass():
            state = STATE_ALARM_ARMED_CUSTOM_BYPASS
        elif self._partition.arming_state.is_arming():
            state = STATE_ALARM_ARMING
        elif self._partition.arming_state.is_disarming():
            state = STATE_ALARM_DISARMING
        elif self._partition.arming_state.is_triggered_police():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Police/Medical"
        elif self._partition.arming_state.is_triggered_fire():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Fire/Smoke"
        elif self._partition.arming_state.is_triggered_gas():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Carbon Monoxide"

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

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.hass.async_add_executor_job(self._disarm)
        await self.coordinator.async_request_refresh()

    def _disarm(self, code=None):
        """Disarm synchronous."""
        try:
            ArmingHelper(self._partition).disarm()
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to disarm {self._name}."
            ) from error

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self.hass.async_add_executor_job(self._arm_home)
        await self.coordinator.async_request_refresh()

    def _arm_home(self):
        """Arm home synchronous."""
        try:
            ArmingHelper(self._partition).arm_stay()
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm home {self._name}."
            ) from error

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self.hass.async_add_executor_job(self._arm_away)
        await self.coordinator.async_request_refresh()

    def _arm_away(self, code=None):
        """Arm away synchronous."""
        try:
            ArmingHelper(self._partition).arm_away()
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm away {self._name}."
            ) from error

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        await self.hass.async_add_executor_job(self._arm_night)
        await self.coordinator.async_request_refresh()

    def _arm_night(self, code=None):
        """Arm night synchronous."""
        try:
            ArmingHelper(self._partition).arm_stay_night()
        except BadResultCodeError as error:
            raise HomeAssistantError(
                f"TotalConnect failed to arm night {self._name}."
            ) from error
