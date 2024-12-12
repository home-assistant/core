"""Collection of helpers."""

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)

from tests.common import MockEntity


class MockAlarm(MockEntity, AlarmControlPanelEntity):
    """Mock Alarm control panel class."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
        | AlarmControlPanelEntityFeature.ARM_VACATION
    )

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._handle("code_arm_required")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        self.schedule_update_ha_state()

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._attr_alarm_state = AlarmControlPanelState.ARMED_NIGHT
        self.schedule_update_ha_state()

    def alarm_arm_vacation(self, code=None):
        """Send arm night command."""
        self._attr_alarm_state = AlarmControlPanelState.ARMED_VACATION
        self.schedule_update_ha_state()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if code == "1234":
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
            self.schedule_update_ha_state()

    def alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
        self.schedule_update_ha_state()
