"""Class to hold all alarm control panel accessories."""
import logging

from pyhap.const import CATEGORY_ALARM_SYSTEM

from homeassistant.components.alarm_control_panel import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_CODE, SERVICE_ALARM_ARM_AWAY, SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT, SERVICE_ALARM_DISARM, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT, STATE_ALARM_TRIGGERED,
    STATE_ALARM_DISARMED)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_CURRENT_SECURITY_STATE, CHAR_TARGET_SECURITY_STATE,
    SERV_SECURITY_SYSTEM)

_LOGGER = logging.getLogger(__name__)

HASS_TO_HOMEKIT = {STATE_ALARM_ARMED_HOME: 0,
                   STATE_ALARM_ARMED_AWAY: 1,
                   STATE_ALARM_ARMED_NIGHT: 2,
                   STATE_ALARM_DISARMED: 3,
                   STATE_ALARM_TRIGGERED: 4}
HOMEKIT_TO_HASS = {c: s for s, c in HASS_TO_HOMEKIT.items()}
STATE_TO_SERVICE = {
    STATE_ALARM_ARMED_AWAY: SERVICE_ALARM_ARM_AWAY,
    STATE_ALARM_ARMED_HOME: SERVICE_ALARM_ARM_HOME,
    STATE_ALARM_ARMED_NIGHT: SERVICE_ALARM_ARM_NIGHT,
    STATE_ALARM_DISARMED: SERVICE_ALARM_DISARM}


@TYPES.register('SecuritySystem')
class SecuritySystem(HomeAccessory):
    """Generate an SecuritySystem accessory for an alarm control panel."""

    def __init__(self, *args):
        """Initialize a SecuritySystem accessory object."""
        super().__init__(*args, category=CATEGORY_ALARM_SYSTEM)
        self._alarm_code = self.config.get(ATTR_CODE)
        self.flag_target_state = False

        serv_alarm = self.add_preload_service(SERV_SECURITY_SYSTEM)
        self.char_current_state = serv_alarm.configure_char(
            CHAR_CURRENT_SECURITY_STATE, value=3)
        self.char_target_state = serv_alarm.configure_char(
            CHAR_TARGET_SECURITY_STATE, value=3,
            setter_callback=self.set_security_state)

    def set_security_state(self, value):
        """Move security state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set security state to %d',
                      self.entity_id, value)
        self.flag_target_state = True
        hass_value = HOMEKIT_TO_HASS[value]
        service = STATE_TO_SERVICE[hass_value]

        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._alarm_code:
            params[ATTR_CODE] = self._alarm_code
        self.hass.services.call(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update security state after state changed."""
        hass_state = new_state.state
        if hass_state in HASS_TO_HOMEKIT:
            current_security_state = HASS_TO_HOMEKIT[hass_state]
            self.char_current_state.set_value(current_security_state)
            _LOGGER.debug('%s: Updated current state to %s (%d)',
                          self.entity_id, hass_state, current_security_state)

            # SecuritySystemTargetState does not support triggered
            if not self.flag_target_state and \
                    hass_state != STATE_ALARM_TRIGGERED:
                self.char_target_state.set_value(current_security_state)
            self.flag_target_state = False
