"""Each ElkM1 area will be created as a separate alarm_control_panel."""
import logging

from elkm1_lib.const import AlarmState, ArmedStatus, ArmLevel, ArmUpState
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    AlarmControlPanel,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv

from . import (
    SERVICE_ALARM_ARM_HOME_INSTANT,
    SERVICE_ALARM_ARM_NIGHT_INSTANT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISPLAY_MESSAGE,
    ElkAttachedEntity,
    create_elk_entities,
)
from .const import DOMAIN

ELK_ALARM_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID, default=[]): cv.entity_ids,
        vol.Required(ATTR_CODE): vol.All(vol.Coerce(int), vol.Range(0, 999999)),
    }
)

DISPLAY_MESSAGE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID, default=[]): cv.entity_ids,
        vol.Optional("clear", default=2): vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
        vol.Optional("beep", default=False): cv.boolean,
        vol.Optional("timeout", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=65535)
        ),
        vol.Optional("line1", default=""): cv.string,
        vol.Optional("line2", default=""): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ElkM1 alarm platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    elk = elk_data["elk"]
    areas_with_keypad = set()
    for keypad in elk.keypads:
        areas_with_keypad.add(keypad.area)

    areas = []
    for area in elk.areas:
        if area.index in areas_with_keypad or elk_data["auto_configure"] is False:
            areas.append(area)
    create_elk_entities(elk_data, areas, "area", ElkArea, entities)
    async_add_entities(entities, True)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_ALARM_ARM_VACATION,
        ELK_ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_vacation",
    )
    platform.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME_INSTANT,
        ELK_ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_home_instant",
    )
    platform.async_register_entity_service(
        SERVICE_ALARM_ARM_NIGHT_INSTANT,
        ELK_ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_night_instant",
    )
    platform.async_register_entity_service(
        SERVICE_ALARM_DISPLAY_MESSAGE,
        DISPLAY_MESSAGE_SERVICE_SCHEMA,
        "async_display_message",
    )


class ElkArea(ElkAttachedEntity, AlarmControlPanel):
    """Representation of an Area / Partition within the ElkM1 alarm panel."""

    def __init__(self, element, elk, elk_data):
        """Initialize Area as Alarm Control Panel."""
        super().__init__(element, elk, elk_data)
        self._changed_by_keypad = None
        self._state = None

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes."""
        await super().async_added_to_hass()
        for keypad in self._elk.keypads:
            keypad.add_callback(self._watch_keypad)

    def _watch_keypad(self, keypad, changeset):
        if keypad.area != self._element.index:
            return
        if changeset.get("last_user") is not None:
            self._changed_by_keypad = keypad.name
            self.async_write_ha_state()

    @property
    def code_format(self):
        """Return the alarm code format."""
        return FORMAT_NUMBER

    @property
    def state(self):
        """Return the state of the element."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def device_state_attributes(self):
        """Attributes of the area."""
        attrs = self.initial_attrs()
        elmt = self._element
        attrs["is_exit"] = elmt.is_exit
        attrs["timer1"] = elmt.timer1
        attrs["timer2"] = elmt.timer2
        if elmt.armed_status is not None:
            attrs["armed_status"] = ArmedStatus(elmt.armed_status).name.lower()
        if elmt.arm_up_state is not None:
            attrs["arm_up_state"] = ArmUpState(elmt.arm_up_state).name.lower()
        if elmt.alarm_state is not None:
            attrs["alarm_state"] = AlarmState(elmt.alarm_state).name.lower()
        attrs["changed_by_keypad"] = self._changed_by_keypad
        return attrs

    def _element_changed(self, element, changeset):
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
            self._state = (
                STATE_ALARM_ARMING if self._element.is_exit else STATE_ALARM_PENDING
            )
        else:
            self._state = elk_state_to_hass_state[self._element.armed_status]

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
        """Send arm night command."""
        self._element.arm(ArmLevel.ARMED_NIGHT.value, int(code))

    async def async_alarm_arm_home_instant(self, code=None):
        """Send arm stay instant command."""
        self._element.arm(ArmLevel.ARMED_STAY_INSTANT.value, int(code))

    async def async_alarm_arm_night_instant(self, code=None):
        """Send arm night instant command."""
        self._element.arm(ArmLevel.ARMED_NIGHT_INSTANT.value, int(code))

    async def async_alarm_arm_vacation(self, code=None):
        """Send arm vacation command."""
        self._element.arm(ArmLevel.ARMED_VACATION.value, int(code))

    async def async_display_message(self, clear, beep, timeout, line1, line2):
        """Display a message on all keypads for the area."""
        self._element.display_message(clear, beep, timeout, line1, line2)
