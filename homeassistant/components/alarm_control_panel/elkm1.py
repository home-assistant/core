"""
Each ElkM1 area will be created as a separate alarm_control_panel in HASS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.elkm1/
"""

import voluptuous as vol
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    ATTR_CODE, ATTR_ENTITY_ID, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_ARMING, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
from homeassistant.components.elkm1 import (
    DOMAIN as ELK_DOMAIN, create_elk_entities, ElkEntity)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)

DEPENDENCIES = [ELK_DOMAIN]

SIGNAL_ARM_ENTITY = 'elkm1_arm'
SIGNAL_DISPLAY_MESSAGE = 'elkm1_display_message'

ELK_ALARM_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID, default=[]): cv.entity_ids,
    vol.Required(ATTR_CODE): vol.All(vol.Coerce(int), vol.Range(0, 999999)),
})

DISPLAY_MESSAGE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID, default=[]): cv.entity_ids,
    vol.Optional('clear', default=2): vol.In([0, 1, 2]),
    vol.Optional('beep', default=False): cv.boolean,
    vol.Optional('timeout', default=0): vol.Range(min=0, max=65535),
    vol.Optional('line1', default=''): cv.string,
    vol.Optional('line2', default=''): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the ElkM1 alarm platform."""
    if discovery_info is None:
        return

    elk = hass.data[ELK_DOMAIN]['elk']
    entities = create_elk_entities(hass, elk.areas, 'area', ElkArea, [])
    async_add_entities(entities, True)

    def _dispatch(signal, entity_ids, *args):
        for entity_id in entity_ids:
            async_dispatcher_send(
                hass, '{}_{}'.format(signal, entity_id), *args)

    def _arm_service(service):
        entity_ids = service.data.get(ATTR_ENTITY_ID, [])
        arm_level = _arm_services().get(service.service)
        args = (arm_level, service.data.get(ATTR_CODE))
        _dispatch(SIGNAL_ARM_ENTITY, entity_ids, *args)

    for service in _arm_services():
        hass.services.async_register(
            alarm.DOMAIN, service, _arm_service, ELK_ALARM_SERVICE_SCHEMA)

    def _display_message_service(service):
        entity_ids = service.data.get(ATTR_ENTITY_ID, [])
        data = service.data
        args = (data['clear'], data['beep'], data['timeout'],
                data['line1'], data['line2'])
        _dispatch(SIGNAL_DISPLAY_MESSAGE, entity_ids, *args)

    hass.services.async_register(
        alarm.DOMAIN, 'elkm1_alarm_display_message',
        _display_message_service, DISPLAY_MESSAGE_SERVICE_SCHEMA)


def _arm_services():
    from elkm1_lib.const import ArmLevel

    return {
        'elkm1_alarm_arm_vacation': ArmLevel.ARMED_VACATION.value,
        'elkm1_alarm_arm_home_instant': ArmLevel.ARMED_STAY_INSTANT.value,
        'elkm1_alarm_arm_night_instant': ArmLevel.ARMED_NIGHT_INSTANT.value,
    }


class ElkArea(ElkEntity, alarm.AlarmControlPanel):
    """Representation of an Area / Partition within the ElkM1 alarm panel."""

    def __init__(self, element, elk, elk_data):
        """Initialize Area as Alarm Control Panel."""
        super().__init__(element, elk, elk_data)
        self._changed_by_entity_id = ''
        self._state = None

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes."""
        await super().async_added_to_hass()
        for keypad in self._elk.keypads:
            keypad.add_callback(self._watch_keypad)
        async_dispatcher_connect(
            self.hass, '{}_{}'.format(SIGNAL_ARM_ENTITY, self.entity_id),
            self._arm_service)
        async_dispatcher_connect(
            self.hass, '{}_{}'.format(SIGNAL_DISPLAY_MESSAGE, self.entity_id),
            self._display_message)

    def _watch_keypad(self, keypad, changeset):
        if keypad.area != self._element.index:
            return
        if changeset.get('last_user') is not None:
            self._changed_by_entity_id = self.hass.data[
                ELK_DOMAIN]['keypads'].get(keypad.index, '')
            self.async_schedule_update_ha_state(True)

    @property
    def code_format(self):
        """Return the alarm code format."""
        return '^[0-9]{4}([0-9]{2})?$'

    @property
    def state(self):
        """Return the state of the element."""
        return self._state

    @property
    def device_state_attributes(self):
        """Attributes of the area."""
        from elkm1_lib.const import AlarmState, ArmedStatus, ArmUpState

        attrs = self.initial_attrs()
        elmt = self._element
        attrs['is_exit'] = elmt.is_exit
        attrs['timer1'] = elmt.timer1
        attrs['timer2'] = elmt.timer2
        if elmt.armed_status is not None:
            attrs['armed_status'] = \
                ArmedStatus(elmt.armed_status).name.lower()
        if elmt.arm_up_state is not None:
            attrs['arm_up_state'] = ArmUpState(elmt.arm_up_state).name.lower()
        if elmt.alarm_state is not None:
            attrs['alarm_state'] = AlarmState(elmt.alarm_state).name.lower()
        attrs['changed_by_entity_id'] = self._changed_by_entity_id
        return attrs

    def _element_changed(self, element, changeset):
        from elkm1_lib.const import ArmedStatus

        elk_state_to_hass_state = {
            ArmedStatus.DISARMED.value: STATE_ALARM_DISARMED,
            ArmedStatus.ARMED_AWAY.value: STATE_ALARM_ARMED_AWAY,
            ArmedStatus.ARMED_STAY.value: STATE_ALARM_ARMED_HOME,
            ArmedStatus.ARMED_STAY_INSTANT.value: STATE_ALARM_ARMED_HOME,
            ArmedStatus.ARMED_TO_NIGHT.value: STATE_ALARM_ARMED_NIGHT,
            ArmedStatus.ARMED_TO_NIGHT_INSTANT.value: STATE_ALARM_ARMED_NIGHT,
            ArmedStatus.ARMED_TO_VACATION.value: STATE_ALARM_ARMED_AWAY,
        }

        if self._element.alarm_state is None:
            self._state = None
        elif self._area_is_in_alarm_state():
            self._state = STATE_ALARM_TRIGGERED
        elif self._entry_exit_timer_is_running():
            self._state = STATE_ALARM_ARMING \
                if self._element.is_exit else STATE_ALARM_PENDING
        else:
            self._state = elk_state_to_hass_state[self._element.armed_status]

    def _entry_exit_timer_is_running(self):
        return self._element.timer1 > 0 or self._element.timer2 > 0

    def _area_is_in_alarm_state(self):
        from elkm1_lib.const import AlarmState

        return self._element.alarm_state >= AlarmState.FIRE_ALARM.value

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        self._element.disarm(int(code))

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        from elkm1_lib.const import ArmLevel

        self._element.arm(ArmLevel.ARMED_STAY.value, int(code))

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        from elkm1_lib.const import ArmLevel

        self._element.arm(ArmLevel.ARMED_AWAY.value, int(code))

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        from elkm1_lib.const import ArmLevel

        self._element.arm(ArmLevel.ARMED_NIGHT.value, int(code))

    async def _arm_service(self, arm_level, code):
        self._element.arm(arm_level, code)

    async def _display_message(self, clear, beep, timeout, line1, line2):
        """Display a message on all keypads for the area."""
        self._element.display_message(clear, beep, timeout, line1, line2)
