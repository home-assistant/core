"""Class to hold all alarm control panel accessories."""
import logging

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT, STATE_ALARM_DISARMED,
    ATTR_ENTITY_ID, ATTR_CODE)

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    CATEGORY_ALARM_SYSTEM, SERV_SECURITY_SYSTEM,
    CHAR_CURRENT_SECURITY_STATE, CHAR_TARGET_SECURITY_STATE)

_LOGGER = logging.getLogger(__name__)

HASS_TO_HOMEKIT = {STATE_ALARM_DISARMED: 3, STATE_ALARM_ARMED_HOME: 0,
                   STATE_ALARM_ARMED_AWAY: 1, STATE_ALARM_ARMED_NIGHT: 2}
HOMEKIT_TO_HASS = {c: s for s, c in HASS_TO_HOMEKIT.items()}
STATE_TO_SERVICE = {STATE_ALARM_DISARMED: 'alarm_disarm',
                    STATE_ALARM_ARMED_HOME: 'alarm_arm_home',
                    STATE_ALARM_ARMED_AWAY: 'alarm_arm_away',
                    STATE_ALARM_ARMED_NIGHT: 'alarm_arm_night'}


@TYPES.register('SecuritySystem')
class SecuritySystem(HomeAccessory):
    """Generate an SecuritySystem accessory for an alarm control panel."""

    def __init__(self, hass, entity_id, display_name, alarm_code, **kwargs):
        """Initialize a SecuritySystem accessory object."""
        super().__init__(display_name, entity_id,
                         CATEGORY_ALARM_SYSTEM, **kwargs)

        self.hass = hass
        self.entity_id = entity_id
        self._alarm_code = alarm_code

        self.flag_target_state = False

        serv_alarm = add_preload_service(self, SERV_SECURITY_SYSTEM)
        self.char_current_state = serv_alarm. \
            get_characteristic(CHAR_CURRENT_SECURITY_STATE)
        self.char_current_state.value = 3
        self.char_target_state = serv_alarm. \
            get_characteristic(CHAR_TARGET_SECURITY_STATE)
        self.char_target_state.value = 3

        self.char_target_state.setter_callback = self.set_security_state

    def set_security_state(self, value):
        """Move security state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set security state to %d',
                      self.entity_id, value)
        self.flag_target_state = True
        self.char_target_state.set_value(value, should_callback=False)
        hass_value = HOMEKIT_TO_HASS[value]
        service = STATE_TO_SERVICE[hass_value]

        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._alarm_code:
            params[ATTR_CODE] = self._alarm_code
        self.hass.services.call('alarm_control_panel', service, params)

    def update_state(self, entity_id=None, old_state=None, new_state=None):
        """Update security state after state changed."""
        if new_state is None:
            return

        hass_state = new_state.state
        if hass_state not in HASS_TO_HOMEKIT:
            return

        current_security_state = HASS_TO_HOMEKIT[hass_state]
        self.char_current_state.set_value(current_security_state,
                                          should_callback=False)
        _LOGGER.debug('%s: Updated current state to %s (%d)',
                      self.entity_id, hass_state, current_security_state)

        if not self.flag_target_state:
            self.char_target_state.set_value(current_security_state,
                                             should_callback=False)
        if self.char_target_state.value == self.char_current_state.value:
            self.flag_target_state = False
