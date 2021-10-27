"""Support for Lupusec System alarm control panels."""
from datetime import timedelta

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

from . import DOMAIN as LUPUSEC_DOMAIN, LupusecDevice

ICON = "mdi:security"

SCAN_INTERVAL = timedelta(seconds=2)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an alarm control panel for a Lupusec device."""
    if discovery_info is None:
        return

    data = hass.data[LUPUSEC_DOMAIN]

    alarm_devices = [LupusecAlarm(data, data.lupusec.get_alarm())]

    add_entities(alarm_devices)


class LupusecAlarm(LupusecDevice, AlarmControlPanelEntity):
    """An alarm_control_panel implementation for Lupusec."""

    @property
    def icon(self):
        """Return the icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        if self._device.is_standby:
            state = STATE_ALARM_DISARMED
        elif self._device.is_away:
            state = STATE_ALARM_ARMED_AWAY
        elif self._device.is_home:
            state = STATE_ALARM_ARMED_HOME
        elif self._device.is_alarm_triggered:
            state = STATE_ALARM_TRIGGERED
        else:
            state = None
        return state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._device.set_away()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._device.set_standby()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._device.set_home()
