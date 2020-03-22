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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an alarm control panel for a TotalConnect device."""
    if discovery_info is None:
        return

    alarms = []

    client = hass.data[DOMAIN].client

    for location_id, location in client.locations.items():
        location_name = location.location_name
        alarms.append(TotalConnectAlarm(location_name, location_id, client))
    add_entities(alarms)


class TotalConnectAlarm(alarm.AlarmControlPanel):
    """Represent an TotalConnect status."""

    def __init__(self, name, location_id, client):
        """Initialize the TotalConnect status."""
        self._name = name
        self._location_id = location_id
        self._client = client
        self._state = None
        self._device_state_attributes = {}

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._device_state_attributes

    def update(self):
        """Return the state of the device."""
        self._client.get_armed_status(self._location_id)
        attr = {
            "location_name": self._name,
            "location_id": self._location_id,
            "ac_loss": self._client.locations[self._location_id].ac_loss,
            "low_battery": self._client.locations[self._location_id].low_battery,
            "cover_tampered": self._client.locations[
                self._location_id
            ].is_cover_tampered(),
            "triggered_source": None,
            "triggered_zone": None,
        }

        if self._client.locations[self._location_id].is_disarmed():
            state = STATE_ALARM_DISARMED
        elif self._client.locations[self._location_id].is_armed_home():
            state = STATE_ALARM_ARMED_HOME
        elif self._client.locations[self._location_id].is_armed_night():
            state = STATE_ALARM_ARMED_NIGHT
        elif self._client.locations[self._location_id].is_armed_away():
            state = STATE_ALARM_ARMED_AWAY
        elif self._client.locations[self._location_id].is_armed_custom_bypass():
            state = STATE_ALARM_ARMED_CUSTOM_BYPASS
        elif self._client.locations[self._location_id].is_arming():
            state = STATE_ALARM_ARMING
        elif self._client.locations[self._location_id].is_disarming():
            state = STATE_ALARM_DISARMING
        elif self._client.locations[self._location_id].is_triggered_police():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Police/Medical"
        elif self._client.locations[self._location_id].is_triggered_fire():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Fire/Smoke"
        elif self._client.locations[self._location_id].is_triggered_gas():
            state = STATE_ALARM_TRIGGERED
            attr["triggered_source"] = "Carbon Monoxide"
        else:
            logging.info("Total Connect Client returned unknown status")
            state = None

        self._state = state
        self._device_state_attributes = attr

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._client.disarm(self._location_id)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._client.arm_stay(self._location_id)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._client.arm_away(self._location_id)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._client.arm_stay_night(self._location_id)
