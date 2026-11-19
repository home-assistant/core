"""Class to hold all alarm control panel accessories."""

import logging
from typing import Any, override

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_ALARM_SYSTEM

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelService,
    AlarmControlPanelServiceArgument,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import State, callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_CURRENT_SECURITY_STATE,
    CHAR_TARGET_SECURITY_STATE,
    PROP_VALID_VALUES,
    SERV_SECURITY_SYSTEM,
)

_LOGGER = logging.getLogger(__name__)

HK_ALARM_STAY_ARMED = 0
HK_ALARM_AWAY_ARMED = 1
HK_ALARM_NIGHT_ARMED = 2
HK_ALARM_DISARMED = 3
HK_ALARM_TRIGGERED = 4

HASS_TO_HOMEKIT_CURRENT = {
    AlarmControlPanelState.ARMED_HOME: HK_ALARM_STAY_ARMED,
    AlarmControlPanelState.ARMED_VACATION: HK_ALARM_AWAY_ARMED,
    AlarmControlPanelState.ARMED_AWAY: HK_ALARM_AWAY_ARMED,
    AlarmControlPanelState.ARMED_NIGHT: HK_ALARM_NIGHT_ARMED,
    AlarmControlPanelState.ARMING: HK_ALARM_DISARMED,
    AlarmControlPanelState.DISARMED: HK_ALARM_DISARMED,
    AlarmControlPanelState.TRIGGERED: HK_ALARM_TRIGGERED,
}

HASS_TO_HOMEKIT_TARGET = {
    AlarmControlPanelState.ARMED_HOME: HK_ALARM_STAY_ARMED,
    AlarmControlPanelState.ARMED_VACATION: HK_ALARM_AWAY_ARMED,
    AlarmControlPanelState.ARMED_AWAY: HK_ALARM_AWAY_ARMED,
    AlarmControlPanelState.ARMED_NIGHT: HK_ALARM_NIGHT_ARMED,
    AlarmControlPanelState.ARMING: HK_ALARM_AWAY_ARMED,
    AlarmControlPanelState.DISARMED: HK_ALARM_DISARMED,
}

HASS_TO_HOMEKIT_SERVICES = {
    AlarmControlPanelService.ARM_HOME: HK_ALARM_STAY_ARMED,
    AlarmControlPanelService.ARM_AWAY: HK_ALARM_AWAY_ARMED,
    AlarmControlPanelService.ARM_NIGHT: HK_ALARM_NIGHT_ARMED,
    AlarmControlPanelService.DISARM: HK_ALARM_DISARMED,
}

HK_TO_SERVICE = {
    HK_ALARM_AWAY_ARMED: AlarmControlPanelService.ARM_AWAY,
    HK_ALARM_STAY_ARMED: AlarmControlPanelService.ARM_HOME,
    HK_ALARM_NIGHT_ARMED: AlarmControlPanelService.ARM_NIGHT,
    HK_ALARM_DISARMED: AlarmControlPanelService.DISARM,
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
        self._skipped: set[tuple[str, int]] = set()

        supported_states = state.attributes.get(
            EntityStateAttribute.SUPPORTED_FEATURES,
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
        default_current_states = current_char.properties.get(PROP_VALID_VALUES)
        default_target_services = target_char.properties.get(PROP_VALID_VALUES)

        # Both characteristics start at 0 (stay armed). Panels without
        # ARM_HOME drop 0 from the valid values below, and HAP-python logs an
        # error when the current value is outside the new set. Disarmed is
        # always valid, so start from it.
        current_char.set_value(HK_ALARM_DISARMED, should_notify=False)
        target_char.set_value(HK_ALARM_DISARMED, should_notify=False)

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
            value=HASS_TO_HOMEKIT_CURRENT[AlarmControlPanelState.DISARMED],
            valid_values={
                key: val
                for key, val in default_current_states.items()
                if val in current_supported_states
            },
        )
        self.char_target_state = serv_alarm.configure_char(
            CHAR_TARGET_SECURITY_STATE,
            value=HASS_TO_HOMEKIT_SERVICES[AlarmControlPanelService.DISARM],
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
            params[AlarmControlPanelServiceArgument.CODE] = self._alarm_code
        self.async_call_service(ALARM_CONTROL_PANEL_DOMAIN, service, params)

    def _set_if_valid(self, char: Characteristic, value: int) -> bool:
        """Push value to char, or skip (returning False) if not advertised.

        The characteristic's valid values are frozen at build time; pushing a
        value outside that set would raise ValueError in pyhap. A skip is
        logged once per value, as only a rebuild can change the outcome.
        """
        name = char.display_name
        if value in char.properties[PROP_VALID_VALUES].values():
            char.set_value(value)
            return True
        if (name, value) not in self._skipped:
            self._skipped.add((name, value))
            _LOGGER.warning(
                "%s: Skipping unsupported %s value %d", self.entity_id, name, value
            )
        return False

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update security state after state changed."""
        hass_state: str | AlarmControlPanelState = new_state.state
        if hass_state in {"None", STATE_UNKNOWN, STATE_UNAVAILABLE}:
            # Bail out early for no state, unknown or unavailable
            return
        hass_state = AlarmControlPanelState(hass_state)
        current_state = HASS_TO_HOMEKIT_CURRENT.get(hass_state)
        target_state = HASS_TO_HOMEKIT_TARGET.get(hass_state)
        if current_state is not None and self._set_if_valid(
            self.char_current_state, current_state
        ):
            _LOGGER.debug(
                "%s: Updated current state to %s (%d)",
                self.entity_id,
                hass_state,
                current_state,
            )
        if target_state is None:
            return
        if (
            hass_state is AlarmControlPanelState.ARMING
            and target_state
            not in self.char_target_state.properties[PROP_VALID_VALUES].values()
        ):
            # Arming doesn't say which mode is pending, so keep the current target
            return
        self._set_if_valid(self.char_target_state, target_state)
