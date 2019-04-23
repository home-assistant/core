"""Support for Homekit Alarm Control Panel."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED)

from . import KNOWN_DEVICES, HomeKitEntity

ICON = 'mdi:security'

_LOGGER = logging.getLogger(__name__)

CURRENT_STATE_MAP = {
    0: STATE_ALARM_ARMED_HOME,
    1: STATE_ALARM_ARMED_AWAY,
    2: STATE_ALARM_ARMED_NIGHT,
    3: STATE_ALARM_DISARMED,
    4: STATE_ALARM_TRIGGERED,
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
    accessory = hass.data[KNOWN_DEVICES][discovery_info['serial']]
    add_entities([HomeKitAlarmControlPanel(accessory, discovery_info)],
                 True)


class HomeKitAlarmControlPanel(HomeKitEntity, AlarmControlPanel):
    """Representation of a Homekit Alarm Control Panel."""

    def __init__(self, *args):
        """Initialise the Alarm Control Panel."""
        super().__init__(*args)
        self._state = None
        self._battery_level = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes
        return [
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT,
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET,
            CharacteristicsTypes.BATTERY_LEVEL,
        ]

    def _update_security_system_state_current(self, value):
        self._state = CURRENT_STATE_MAP[value]

    def _update_battery_level(self, value):
        self._battery_level = value

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.set_alarm_state(STATE_ALARM_DISARMED, code)

    async def async_alarm_arm_away(self, code=None):
        """Send arm command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_AWAY, code)

    async def async_alarm_arm_home(self, code=None):
        """Send stay command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_HOME, code)

    async def async_alarm_arm_night(self, code=None):
        """Send night command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_NIGHT, code)

    async def set_alarm_state(self, state, code=None):
        """Send state command."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['security-system-state.target'],
                            'value': TARGET_STATE_MAP[state]}]
        await self._accessory.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._battery_level is None:
            return None

        return {
            ATTR_BATTERY_LEVEL: self._battery_level,
        }
