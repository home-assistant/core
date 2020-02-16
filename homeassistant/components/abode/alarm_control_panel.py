"""Support for Abode Security System alarm control panels."""
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)

from . import AbodeDevice
from .const import ATTRIBUTION, DOMAIN

ICON = "mdi:security"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode alarm control panel device."""
    data = hass.data[DOMAIN]
    async_add_entities(
        [AbodeAlarm(data, await hass.async_add_executor_job(data.abode.get_alarm))]
    )


class AbodeAlarm(AbodeDevice, alarm.AlarmControlPanel):
    """An alarm_control_panel implementation for Abode."""

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
        else:
            state = None
        return state

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._device.set_standby()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._device.set_home()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._device.set_away()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self._device.device_id,
            "battery_backup": self._device.battery,
            "cellular_backup": self._device.is_cellular,
        }
