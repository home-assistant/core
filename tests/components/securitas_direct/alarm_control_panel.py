"""Support for Securitas Direct (AKA Verisure EU) alarm control panels."""

import datetime

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
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)

from . import DOMAIN

# some reported by @furetto72@Italy
SECURITAS_STATUS = {
    STATE_ALARM_DISARMED: ["0", ("1", "32")],
    STATE_ALARM_ARMED_HOME: ["P", ("311", "202")],
    STATE_ALARM_ARMED_NIGHT: [("Q", "C"), ("46",)],
    STATE_ALARM_ARMED_AWAY: [("1", "A"), ("2", "31")],
    STATE_ALARM_ARMED_CUSTOM_BYPASS: ["3", ("204",)],
    STATE_ALARM_TRIGGERED: ["???", ("13", "24")],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Securitas platform."""

    add_entities([SecuritasAlarm(hass.data[DOMAIN].client)])


class SecuritasAlarm(alarm.AlarmControlPanelEntity):
    """Representation of a Securitas alarm status."""

    def __init__(self, client):
        """Initialize the Securitas alarm panel."""
        self.client = client
        self._state = None
        self._changed_by = None
        self._device = ""
        self._time = None
        self._message = ""

    def get_arm_state(self):
        res = self.client.alarm.get_status()
        for k, v in SECURITAS_STATUS.items():
            if res["STATUS"] in v[0]:
                return k

    def activate_state(self, code, state_action):
        """ Validates the inserted code against configured one """

        if self.client.code is None or self.client.code == code:
            self._state = STATE_ALARM_DISARMING
            self.hass.states.set(self.entity_id, STATE_ALARM_DISARMING)
            state_action()
            self.client.update_overview(no_throttle=True)

    @property
    def name(self):
        """Return the name of the device."""
        return f"securitas_{self.client.installation_alias or self.client.installation_num}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return alarm.FORMAT_NUMBER

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    @property
    def changed_by(self):
        """Return the last change triggered by."""
        return self._changed_by

    def update(self):
        """Update alarm status, from last alarm setting register or EST"""
        self.client.update_overview()
        status = self.client.overview
        try:
            for k, v in SECURITAS_STATUS.items():
                if status["@type"] in v[1]:
                    self._state = k
                    self._changed_by = f"{status['@user'] or status['@myverisureUser'] or ''}@{status['@source']}"
                    self._device = status["@device"]
                    self._time = datetime.datetime.strptime(
                        status["@time"], "%y%m%d%H%M%S"
                    )
                    self._message = status["@alias"]
                    break
        except (KeyError, TypeError):
            if self._state is None:
                self._state = self.get_arm_state() or STATE_ALARM_PENDING

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "device": self._device,
            "time": self._time,
            "message": self._message,
            "alias": self.client.installation_alias,
        }

    def alarm_disarm(self, code=None):
        """Send disarm command."""

        self.activate_state(code, self.client.alarm.disconnect)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""

        self.activate_state(code, self.client.alarm.activate_day_mode)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""

        self.activate_state(code, self.client.alarm.activate_total_mode)

    def alarm_arm_night(self, code=None):
        """Send arm home command."""

        self.activate_state(code, self.client.alarm.activate_night_mode)

    def alarm_arm_custom_bypass(self, code=None):
        """Send arm perimeter command."""

        self.activate_state(code, self.client.alarm.activate_perimeter_mode)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""

        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT
