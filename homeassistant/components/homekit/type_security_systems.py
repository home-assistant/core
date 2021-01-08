"""Class to hold all alarm control panel accessories."""
import logging

from pyhap.const import CATEGORY_ALARM_SYSTEM
from pyhap.loader import get_loader

from homeassistant.components.alarm_control_panel import DOMAIN
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_CURRENT_SECURITY_STATE,
    CHAR_TARGET_SECURITY_STATE,
    SERV_SECURITY_SYSTEM,
)

_LOGGER = logging.getLogger(__name__)

HASS_TO_HOMEKIT = {
    STATE_ALARM_ARMED_HOME: 0,
    STATE_ALARM_ARMED_AWAY: 1,
    STATE_ALARM_ARMED_NIGHT: 2,
    STATE_ALARM_DISARMED: 3,
    STATE_ALARM_TRIGGERED: 4,
}

HASS_TO_HOMEKIT_SERVICES = {
    SERVICE_ALARM_ARM_HOME: 0,
    SERVICE_ALARM_ARM_AWAY: 1,
    SERVICE_ALARM_ARM_NIGHT: 2,
    SERVICE_ALARM_DISARM: 3,
}

HOMEKIT_TO_HASS = {c: s for s, c in HASS_TO_HOMEKIT.items()}

STATE_TO_SERVICE = {
    STATE_ALARM_ARMED_AWAY: SERVICE_ALARM_ARM_AWAY,
    STATE_ALARM_ARMED_HOME: SERVICE_ALARM_ARM_HOME,
    STATE_ALARM_ARMED_NIGHT: SERVICE_ALARM_ARM_NIGHT,
    STATE_ALARM_DISARMED: SERVICE_ALARM_DISARM,
}


@TYPES.register("SecuritySystem")
class SecuritySystem(HomeAccessory):
    """Generate an SecuritySystem accessory for an alarm control panel."""

    def __init__(self, *args):
        """Initialize a SecuritySystem accessory object."""
        super().__init__(*args, category=CATEGORY_ALARM_SYSTEM)
        state = self.hass.states.get(self.entity_id)
        self._alarm_code = self.config.get(ATTR_CODE)

        supported_states = state.attributes.get(
            ATTR_SUPPORTED_FEATURES,
            (
                SUPPORT_ALARM_ARM_HOME
                | SUPPORT_ALARM_ARM_AWAY
                | SUPPORT_ALARM_ARM_NIGHT
                | SUPPORT_ALARM_TRIGGER
            ),
        )

        loader = get_loader()
        default_current_states = loader.get_char(
            "SecuritySystemCurrentState"
        ).properties.get("ValidValues")
        default_target_services = loader.get_char(
            "SecuritySystemTargetState"
        ).properties.get("ValidValues")

        current_supported_states = [
            HASS_TO_HOMEKIT[STATE_ALARM_DISARMED],
            HASS_TO_HOMEKIT[STATE_ALARM_TRIGGERED],
        ]
        target_supported_services = [HASS_TO_HOMEKIT_SERVICES[SERVICE_ALARM_DISARM]]

        if supported_states & SUPPORT_ALARM_ARM_HOME:
            current_supported_states.append(HASS_TO_HOMEKIT[STATE_ALARM_ARMED_HOME])
            target_supported_services.append(
                HASS_TO_HOMEKIT_SERVICES[SERVICE_ALARM_ARM_HOME]
            )

        if supported_states & SUPPORT_ALARM_ARM_AWAY:
            current_supported_states.append(HASS_TO_HOMEKIT[STATE_ALARM_ARMED_AWAY])
            target_supported_services.append(
                HASS_TO_HOMEKIT_SERVICES[SERVICE_ALARM_ARM_AWAY]
            )

        if supported_states & SUPPORT_ALARM_ARM_NIGHT:
            current_supported_states.append(HASS_TO_HOMEKIT[STATE_ALARM_ARMED_NIGHT])
            target_supported_services.append(
                HASS_TO_HOMEKIT_SERVICES[SERVICE_ALARM_ARM_NIGHT]
            )

        new_current_states = {
            key: val
            for key, val in default_current_states.items()
            if val in current_supported_states
        }
        new_target_services = {
            key: val
            for key, val in default_target_services.items()
            if val in target_supported_services
        }

        serv_alarm = self.add_preload_service(SERV_SECURITY_SYSTEM)
        self.char_current_state = serv_alarm.configure_char(
            CHAR_CURRENT_SECURITY_STATE,
            value=HASS_TO_HOMEKIT[STATE_ALARM_DISARMED],
            valid_values=new_current_states,
        )
        self.char_target_state = serv_alarm.configure_char(
            CHAR_TARGET_SECURITY_STATE,
            value=HASS_TO_HOMEKIT_SERVICES[SERVICE_ALARM_DISARM],
            valid_values=new_target_services,
            setter_callback=self.set_security_state,
        )

        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def set_security_state(self, value):
        """Move security state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set security state to %d", self.entity_id, value)
        hass_value = HOMEKIT_TO_HASS[value]
        service = STATE_TO_SERVICE[hass_value]

        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._alarm_code:
            params[ATTR_CODE] = self._alarm_code
        self.call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state):
        """Update security state after state changed."""
        hass_state = new_state.state
        if hass_state in HASS_TO_HOMEKIT:
            current_security_state = HASS_TO_HOMEKIT[hass_state]
            if self.char_current_state.value != current_security_state:
                self.char_current_state.set_value(current_security_state)
                _LOGGER.debug(
                    "%s: Updated current state to %s (%d)",
                    self.entity_id,
                    hass_state,
                    current_security_state,
                )

            # SecuritySystemTargetState does not support triggered
            if (
                hass_state != STATE_ALARM_TRIGGERED
                and self.char_target_state.value != current_security_state
            ):
                self.char_target_state.set_value(current_security_state)
