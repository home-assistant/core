"""
Support for Homekit Alarm Control Panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (HomeKitEntity,
                                                         KNOWN_ACCESSORIES)
from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_TRIGGERED)
from homeassistant.const import ATTR_BATTERY_LEVEL

DEPENDENCIES = ['homekit_controller']

ICON = 'mdi:security'

_LOGGER = logging.getLogger(__name__)

CURRENT_STATE_MAP = {
    0: STATE_ALARM_ARMED_HOME,
    1: STATE_ALARM_ARMED_AWAY,
    2: STATE_ALARM_ARMED_NIGHT,
    3: STATE_ALARM_DISARMED,
    4: STATE_ALARM_TRIGGERED
}

TARGET_STATE_MAP = {
    STATE_ALARM_ARMED_HOME: 0,
    STATE_ALARM_ARMED_AWAY: 1,
    STATE_ALARM_ARMED_NIGHT: 2,
    STATE_ALARM_DISARMED: 3,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit Alarm Control Panel support."""
    if discovery_info is None:
        return
    accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
    add_entities([HomeKitAlarmControlPanel(accessory, discovery_info)],
                 True)


class HomeKitAlarmControlPanel(HomeKitEntity, AlarmControlPanel):
    """Representation of a Homekit Alarm Control Panel."""

    def __init__(self, *args):
        """Initialise the Alarm Control Panel."""
        super().__init__(*args)
        self._state = None
        self._battery_level = None

    def update_characteristics(self, characteristics):
        """Synchronise the Alarm Control Panel state with Home Assistant."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = CharacteristicsTypes.get_short(ctype)
            if ctype == "security-system-state.current":
                self._chars['security-system-state.current'] = \
                    characteristic['iid']
                self._state = CURRENT_STATE_MAP[characteristic['value']]
            elif ctype == "security-system-state.target":
                self._chars['security-system-state.target'] = \
                    characteristic['iid']
            elif ctype == "battery-level":
                self._chars['battery-level'] = characteristic['iid']
                self._battery_level = characteristic['value']

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.set_alarm_state(STATE_ALARM_DISARMED, code)

    def alarm_arm_away(self, code=None):
        """Send arm command."""
        self.set_alarm_state(STATE_ALARM_ARMED_AWAY, code)

    def alarm_arm_home(self, code=None):
        """Send stay command."""
        self.set_alarm_state(STATE_ALARM_ARMED_HOME, code)

    def alarm_arm_night(self, code=None):
        """Send night command."""
        self.set_alarm_state(STATE_ALARM_ARMED_NIGHT, code)

    def set_alarm_state(self, state, code=None):
        """Send state command."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['security-system-state.target'],
                            'value': TARGET_STATE_MAP[state]}]
        self.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._battery_level is None:
            return None

        return {
            ATTR_BATTERY_LEVEL: self._battery_level,
        }
