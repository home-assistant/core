"""
Each ElkM1 area will be created as a separate alarm_control_panel in HASS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.elkm1/
"""

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (ATTR_ENTITY_ID, STATE_ALARM_ARMED_AWAY,
                                 STATE_ALARM_ARMED_HOME,
                                 STATE_ALARM_ARMED_NIGHT, STATE_ALARM_ARMING,
                                 STATE_ALARM_DISARMED, STATE_ALARM_PENDING,
                                 STATE_ALARM_TRIGGERED, STATE_UNKNOWN)

from homeassistant.components.elkm1 import (DOMAIN, create_elk_devices,
                                            ElkDeviceBase,
                                            register_elk_service)
from elkm1_lib.const import AlarmState, ArmedStatus, ArmLevel, ArmUpState

DEPENDENCIES = [DOMAIN]

STATE_ALARM_ARMED_VACATION = 'armed_vacation'
STATE_ALARM_ARMED_HOME_INSTANT = 'armed_home_instant'
STATE_ALARM_ARMED_NIGHT_INSTANT = 'armed_night_instant'

SERVICE_TO_ELK = {
    'alarm_arm_vacation': 'async_alarm_arm_vacation',
    'alarm_arm_home_instant': 'async_alarm_arm_home_instant',
    'alarm_arm_night_instant': 'async_alarm_arm_night_instant',
}

DISPLAY_MESSAGE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional('clear', default=2): vol.In([0, 1, 2]),
    vol.Optional('beep', default=False): cv.boolean,
    vol.Optional('timeout', default=0): vol.Range(min=0, max=65535),
    vol.Optional('line1', default=''): cv.string,
    vol.Optional('line2', default=''): cv.string,
})

ELK_STATE_TO_HASS_STATE = {
    ArmedStatus.DISARMED.value:               STATE_ALARM_DISARMED,
    ArmedStatus.ARMED_AWAY.value:             STATE_ALARM_ARMED_AWAY,
    ArmedStatus.ARMED_STAY.value:             STATE_ALARM_ARMED_HOME,
    ArmedStatus.ARMED_STAY_INSTANT.value:     STATE_ALARM_ARMED_HOME,
    ArmedStatus.ARMED_TO_NIGHT.value:         STATE_ALARM_ARMED_NIGHT,
    ArmedStatus.ARMED_TO_NIGHT_INSTANT.value: STATE_ALARM_ARMED_NIGHT,
    ArmedStatus.ARMED_TO_VACATION.value:      STATE_ALARM_ARMED_AWAY,
}


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info):
    """Setup the ElkM1 alarm platform."""

    elk = hass.data[DOMAIN]['elk']
    devices = create_elk_devices(hass, elk.areas, 'area', ElkArea, [])
    async_add_devices(devices, True)

    for service, method in SERVICE_TO_ELK.items():
        register_elk_service(
            hass, alarm.DOMAIN, service, alarm.ALARM_SERVICE_SCHEMA, method)

    register_elk_service(
        hass, alarm.DOMAIN, 'alarm_display_message',
        DISPLAY_MESSAGE_SERVICE_SCHEMA, 'async_alarm_display_message')

    return True


class ElkArea(ElkDeviceBase, alarm.AlarmControlPanel):
    """Representation of an Area / Partition within the ElkM1 alarm panel."""

    def __init__(self, device, hass, config):
        """Initialize Area as Alarm Control Panel."""
        ElkDeviceBase.__init__(self, 'alarm_control_panel', device,
                               hass, config)
        self._changed_by_entity_id = ''

        for keypad in self._elk.keypads:
            keypad.add_callback(self._watch_keypad)

    def _watch_keypad(self, keypad, changeset):
        if keypad.area != self._element.index:
            return
        if changeset.get('last_user') is not None:
            self._changed_by_entity_id = self._hass.data[
                DOMAIN]['keypads'].get(keypad.index, '')
            self.async_schedule_update_ha_state(True)

    @property
    def code_format(self):
        """Return the alarm code format."""
        return '^[0-9]{4}([0-9]{2})?$'

    @property
    def device_state_attributes(self):
        """Attributes of the area."""
        attrs = self.initial_attrs()
        elmt = self._element
        attrs['is_exit'] = elmt.is_exit
        attrs['timer1'] = elmt.timer1
        attrs['timer2'] = elmt.timer2
        attrs['armed_status'] = STATE_UNKNOWN if elmt.armed_status is None \
            else ArmedStatus(elmt.armed_status).name.lower()
        attrs['arm_up_state'] = STATE_UNKNOWN if elmt.arm_up_state is None \
            else ArmUpState(elmt.arm_up_state).name.lower()
        attrs['alarm_state'] = STATE_UNKNOWN if elmt.alarm_state is None \
            else AlarmState(elmt.alarm_state).name.lower()
        attrs['changed_by_entity_id'] = self._changed_by_entity_id
        return attrs

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        if self._element.alarm_state is None:
            self._state = STATE_UNKNOWN
        elif self._area_is_in_alarm_state():
            self._state = STATE_ALARM_TRIGGERED
        elif self._entry_exit_timer_is_running():
            self._state = STATE_ALARM_ARMING \
                if self._element.is_exit else STATE_ALARM_PENDING
        else:
            self._state = ELK_STATE_TO_HASS_STATE[self._element.armed_status]

    def _entry_exit_timer_is_running(self):
        return self._element.timer1 > 0 or self._element.timer2 > 0

    def _area_is_in_alarm_state(self):
        return self._element.alarm_state >= AlarmState.FIRE_ALARM.value

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        self._element.disarm(int(code))

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._element.arm(ArmLevel.ARMED_STAY.value, int(code))

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._element.arm(ArmLevel.ARMED_AWAY.value, int(code))

    async def async_alarm_arm_night(self, code=None):
        """Send arm away command."""
        self._element.arm(ArmLevel.ARMED_NIGHT.value, int(code))

    async def async_alarm_arm_home_instant(self, code):
        """Send arm vacation command."""
        self._element.arm(ArmLevel.ARMED_STAY_INSTANT.value, int(code))

    async def async_alarm_arm_night_instant(self, code):
        """Send arm vacation command."""
        self._element.arm(ArmLevel.ARMED_VACATION.value, int(code))

    async def async_alarm_arm_vacation(self, code):
        """Send arm vacation command."""
        self._element.arm(ArmLevel.ARMED_VACATION.value, int(code))

    async def async_alarm_display_message(
            self, clear, beep, timeout, line1, line2):
        """Display a message on all keypads for the area."""
        self._element.display_message(clear, beep, timeout, line1, line2)
