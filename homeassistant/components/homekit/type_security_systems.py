"""Class to hold all alarm control panel accessories."""
import logging
from typing import Any

from pyhap.const import CATEGORY_ALARM_SYSTEM

from homeassistant.components.alarm_control_panel import (
    DOMAIN,
    AlarmControlPanelEntityFeature,
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
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_CURRENT_SECURITY_STATE,
    CHAR_TARGET_SECURITY_STATE,
    SERV_SECURITY_SYSTEM,
)

_LOGGER = logging.getLogger(__name__)

HK_ALARM_STAY_ARMED = 0
HK_ALARM_AWAY_ARMED = 1
HK_ALARM_NIGHT_ARMED = 2
HK_ALARM_DISARMED = 3
HK_ALARM_TRIGGERED = 4

HASS_TO_HOMEKIT_CURRENT = {
    STATE_ALARM_ARMED_HOME: HK_ALARM_STAY_ARMED,
    STATE_ALARM_ARMED_VACATION: HK_ALARM_AWAY_ARMED,
    STATE_ALARM_ARMED_AWAY: HK_ALARM_AWAY_ARMED,
    STATE_ALARM_ARMED_NIGHT: HK_ALARM_NIGHT_ARMED,
    STATE_ALARM_ARMING: HK_ALARM_DISARMED,
    STATE_ALARM_DISARMED: HK_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED: HK_ALARM_TRIGGERED,
}

HASS_TO_HOMEKIT_TARGET = {
    STATE_ALARM_ARMED_HOME: HK_ALARM_STAY_ARMED,
    STATE_ALARM_ARMED_VACATION: HK_ALARM_AWAY_ARMED,
    STATE_ALARM_ARMED_AWAY: HK_ALARM_AWAY_ARMED,
    STATE_ALARM_ARMED_NIGHT: HK_ALARM_NIGHT_ARMED,
    STATE_ALARM_ARMING: HK_ALARM_AWAY_ARMED,
    STATE_ALARM_DISARMED: HK_ALARM_DISARMED,
}

HASS_TO_HOMEKIT_SERVICES = {
    SERVICE_ALARM_ARM_HOME: HK_ALARM_STAY_ARMED,
    SERVICE_ALARM_ARM_AWAY: HK_ALARM_AWAY_ARMED,
    SERVICE_ALARM_ARM_NIGHT: HK_ALARM_NIGHT_ARMED,
    SERVICE_ALARM_DISARM: HK_ALARM_DISARMED,
}

HK_TO_SERVICE = {
    HK_ALARM_AWAY_ARMED: SERVICE_ALARM_ARM_AWAY,
    HK_ALARM_STAY_ARMED: SERVICE_ALARM_ARM_HOME,
    HK_ALARM_NIGHT_ARMED: SERVICE_ALARM_ARM_NIGHT,
    HK_ALARM_DISARMED: SERVICE_ALARM_DISARM,
}


@TYPES.register("SecuritySystem")
class SecuritySystem(HomeAccessory):
    """Generate an SecuritySystem accessory for an alarm control panel."""

    def __init__(self, *args: Any) -> None:
        """Initialize a SecuritySystem accessory object."""
        super().__init__(*args, category=CATEGORY_ALARM_SYSTEM)
        state = self.hass.states.get(self.entity_id)
        assert state
        self._alarm_code = self.config.get(ATTR_CODE)

        supported_states = state.attributes.get(
            ATTR_SUPPORTED_FEATURES,
            (
                AlarmControlPanelEntityFeature.ARM_HOME
                | AlarmControlPanelEntityFeature.ARM_VACATION
                | AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_NIGHT
                | AlarmControlPanelEntityFeature.TRIGGER
            ),
        )

        serv_alarm = self.add_preload_service(SERV_SECURITY_SYSTEM)
        current_char = serv_alarm.get_characteristic(CHAR_CURRENT_SECURITY_STATE)
        target_char = serv_alarm.get_characteristic(CHAR_TARGET_SECURITY_STATE)
        default_current_states = current_char.properties.get("ValidValues")
        default_target_services = target_char.properties.get("ValidValues")

        current_supported_states = [HK_ALARM_DISARMED, HK_ALARM_TRIGGERED]
        target_supported_services = [HK_ALARM_DISARMED]

        if supported_states & AlarmControlPanelEntityFeature.ARM_HOME:
            current_supported_states.append(HK_ALARM_STAY_ARMED)
            target_supported_services.append(HK_ALARM_STAY_ARMED)

        if supported_states & (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_VACATION
        ):
            current_supported_states.append(HK_ALARM_AWAY_ARMED)
            target_supported_services.append(HK_ALARM_AWAY_ARMED)

        if supported_states & AlarmControlPanelEntityFeature.ARM_NIGHT:
            current_supported_states.append(HK_ALARM_NIGHT_ARMED)
            target_supported_services.append(HK_ALARM_NIGHT_ARMED)

        self.char_current_state = serv_alarm.configure_char(
            CHAR_CURRENT_SECURITY_STATE,
            value=HASS_TO_HOMEKIT_CURRENT[STATE_ALARM_DISARMED],
            valid_values={
                key: val
                for key, val in default_current_states.items()
                if val in current_supported_states
            },
        )
        self.char_target_state = serv_alarm.configure_char(
            CHAR_TARGET_SECURITY_STATE,
            value=HASS_TO_HOMEKIT_SERVICES[SERVICE_ALARM_DISARM],
            valid_values={
                key: val
                for key, val in default_target_services.items()
                if val in target_supported_services
            },
            setter_callback=self.set_security_state,
        )

        # Set the state so it is in sync on initial
        # GET to avoid an event storm after homekit startup
        self.async_update_state(state)

    def set_security_state(self, value: int) -> None:
        """Move security state to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set security state to %d", self.entity_id, value)
        service = HK_TO_SERVICE[value]
        params = {ATTR_ENTITY_ID: self.entity_id}
        if self._alarm_code:
            params[ATTR_CODE] = self._alarm_code
        self.async_call_service(DOMAIN, service, params)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update security state after state changed."""
        hass_state = new_state.state
        if (current_state := HASS_TO_HOMEKIT_CURRENT.get(hass_state)) is not None:
            self.char_current_state.set_value(current_state)
            _LOGGER.debug(
                "%s: Updated current state to %s (%d)",
                self.entity_id,
                hass_state,
                current_state,
            )
        if (target_state := HASS_TO_HOMEKIT_TARGET.get(hass_state)) is not None:
            self.char_target_state.set_value(target_state)
