"""Class to hold all alarm control panel accessories."""

import logging
from typing import Any

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_ALARM_SYSTEM

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
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


DEFAULT_SUPPORTED_FEATURES = (
    AlarmControlPanelEntityFeature.ARM_HOME
    | AlarmControlPanelEntityFeature.ARM_VACATION
    | AlarmControlPanelEntityFeature.ARM_AWAY
    | AlarmControlPanelEntityFeature.ARM_NIGHT
    | AlarmControlPanelEntityFeature.TRIGGER
)


def _supported_states(supported_features: int) -> tuple[list[int], list[int]]:
    """Return the supported (current_states, target_services) for the features.

    Mirrors how HomeKit's valid values are derived from the alarm entity's
    supported_features, so the accessory build and the runtime staleness check
    stay in sync.
    """
    current_supported_states = [HK_ALARM_DISARMED, HK_ALARM_TRIGGERED]
    target_supported_services = [HK_ALARM_DISARMED]

    if supported_features & AlarmControlPanelEntityFeature.ARM_HOME:
        current_supported_states.append(HK_ALARM_STAY_ARMED)
        target_supported_services.append(HK_ALARM_STAY_ARMED)

    if supported_features & (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_VACATION
    ):
        current_supported_states.append(HK_ALARM_AWAY_ARMED)
        target_supported_services.append(HK_ALARM_AWAY_ARMED)

    if supported_features & AlarmControlPanelEntityFeature.ARM_NIGHT:
        current_supported_states.append(HK_ALARM_NIGHT_ARMED)
        target_supported_services.append(HK_ALARM_NIGHT_ARMED)

    return current_supported_states, target_supported_services


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
            ATTR_SUPPORTED_FEATURES, DEFAULT_SUPPORTED_FEATURES
        )

        serv_alarm = self.add_preload_service(SERV_SECURITY_SYSTEM)
        current_char = serv_alarm.get_characteristic(CHAR_CURRENT_SECURITY_STATE)
        target_char = serv_alarm.get_characteristic(CHAR_TARGET_SECURITY_STATE)
        default_current_states = current_char.properties.get(PROP_VALID_VALUES)
        default_target_services = target_char.properties.get(PROP_VALID_VALUES)

        current_supported_states, target_supported_services = _supported_states(
            supported_states
        )

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
        self.async_call_service(ALARM_CONTROL_PANEL_DOMAIN, service, params)

    def _set_or_reload(
        self, char: Characteristic, value: int, currently_supported: list[int]
    ) -> bool:
        """Push value to char; reload or skip if it isn't a valid value.

        The characteristic's valid values are frozen from supported_features at
        accessory build time. A feature change can slip past the reload guard in
        async_update_event_state_callback (e.g. it arrives across an unavailable
        boundary), leaving the frozen set stale. ``currently_supported`` is what
        the entity's *current* supported_features would allow:

        - value valid for the char: push it.
        - value not valid, but the current features do support it: the features
          changed since build -> reload to rebuild the accessory.
        - value not valid and not supported now either: the entity is reporting
          a state it doesn't advertise -> reloading wouldn't help (and would
          loop), so log and skip.

        Returns True if the value was pushed, False otherwise.
        """
        if value in char.properties.get(PROP_VALID_VALUES, {}).values():
            char.set_value(value)
            return True
        if value in currently_supported:
            self.async_reload()
        else:
            _LOGGER.debug(
                "%s: Skipping unsupported security state %d; not in %s",
                self.entity_id,
                value,
                currently_supported,
            )
        return False

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update security state after state changed."""
        hass_state: str | AlarmControlPanelState = new_state.state
        if hass_state in {"None", STATE_UNKNOWN, STATE_UNAVAILABLE}:
            # Bail out early for no state, unknown or unavailable
            return
        if hass_state is not None:
            hass_state = AlarmControlPanelState(hass_state)
        if not hass_state:
            return
        current_state = HASS_TO_HOMEKIT_CURRENT.get(hass_state)
        target_state = HASS_TO_HOMEKIT_TARGET.get(hass_state)
        if current_state is None and target_state is None:
            return
        current_supported, target_supported = _supported_states(
            new_state.attributes.get(
                ATTR_SUPPORTED_FEATURES, DEFAULT_SUPPORTED_FEATURES
            )
        )
        if current_state is not None:
            if not self._set_or_reload(
                self.char_current_state, current_state, current_supported
            ):
                return
            _LOGGER.debug(
                "%s: Updated current state to %s (%d)",
                self.entity_id,
                hass_state,
                current_state,
            )
        if target_state is not None:
            self._set_or_reload(self.char_target_state, target_state, target_supported)
