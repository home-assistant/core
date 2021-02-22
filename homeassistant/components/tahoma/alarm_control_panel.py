"""Support for TaHoma alarm control panels."""
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)

from .const import DOMAIN
from .tahoma_entity import TahomaEntity

COMMAND_ALARM_OFF = "alarmOff"
COMMAND_ALARM_ON = "alarmOn"
COMMAND_ALARM_PARTIAL_1 = "alarmPartial1"
COMMAND_ALARM_PARTIAL_2 = "alarmPartial2"
COMMAND_ARM = "arm"
COMMAND_ARM_PARTIAL_DAY = "armPartialDay"
COMMAND_ARM_PARTIAL_NIGHT = "armPartialNight"
COMMAND_DISARM = "disarm"
COMMAND_PARTIAL = "partial"
COMMAND_SET_ALARM_STATUS = "setAlarmStatus"

CORE_INTRUSION_STATE = "core:IntrusionState"
INTERNAL_CURRENT_ALARM_MODE_STATE = "internal:CurrentAlarmModeState"
INTERNAL_TARGET_ALARM_MODE_STATE = "internal:TargetAlarmModeState"
INTERNAL_INTRUSION_DETECTED_STATE = "internal:IntrusionDetectedState"
MYFOX_ALARM_STATUS_STATE = "myfox:AlarmStatusState"
VERISURE_ALARM_PANEL_MAIN_ARM_TYPE_STATE = "verisure:AlarmPanelMainArmTypeState"

STATE_ARMED = "armed"
STATE_ARMED_DAY = "armedDay"
STATE_ARMED_NIGHT = "armedNight"
STATE_DETECTED = "detected"
STATE_DISARMED = "disarmed"
STATE_OFF = "off"
STATE_PARTIAL = "partial"
STATE_ZONE_1 = "zone1"
STATE_ZONE_2 = "zone2"
STATE_PENDING = "pending"
STATE_TOTAL = "total"
STATE_UNDETECTED = "undetected"

MAP_MYFOX_STATUS_STATE = {
    STATE_ARMED: STATE_ALARM_ARMED_AWAY,
    STATE_DISARMED: STATE_ALARM_DISARMED,
    STATE_PARTIAL: STATE_ALARM_ARMED_NIGHT,
}

MAP_INTERNAL_STATUS_STATE = {
    STATE_OFF: STATE_ALARM_DISARMED,
    STATE_ZONE_1: STATE_ALARM_ARMED_HOME,
    STATE_ZONE_2: STATE_ALARM_ARMED_NIGHT,
    STATE_TOTAL: STATE_ALARM_ARMED_AWAY,
}

MAP_VERISURE_STATUS_STATE = {
    STATE_ARMED: STATE_ALARM_ARMED_AWAY,
    STATE_DISARMED: STATE_ALARM_DISARMED,
    STATE_ARMED_DAY: STATE_ALARM_ARMED_HOME,
    STATE_ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma alarm control panel from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        TahomaAlarmControlPanel(device.deviceurl, coordinator)
        for device in data["platforms"][ALARM_CONTROL_PANEL]
    ]

    async_add_entities(entities)


class TahomaAlarmControlPanel(TahomaEntity, AlarmControlPanelEntity):
    """Representation of a TaHoma Alarm Control Panel."""

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.device.widget != "TSKAlarmController"

    @property
    def state(self):
        """Return the state of the device."""
        if self.executor.has_state(
            CORE_INTRUSION_STATE, INTERNAL_INTRUSION_DETECTED_STATE
        ):
            state = self.executor.select_state(
                CORE_INTRUSION_STATE, INTERNAL_INTRUSION_DETECTED_STATE
            )
            if state == STATE_DETECTED:
                return STATE_ALARM_TRIGGERED
            elif state == STATE_PENDING:
                return STATE_ALARM_PENDING

        if (
            self.executor.has_state(INTERNAL_CURRENT_ALARM_MODE_STATE)
            and self.executor.has_state(INTERNAL_TARGET_ALARM_MODE_STATE)
            and self.executor.select_state(INTERNAL_CURRENT_ALARM_MODE_STATE)
            != self.executor.select_state(INTERNAL_TARGET_ALARM_MODE_STATE)
        ):
            return STATE_ALARM_PENDING

        if self.executor.has_state(MYFOX_ALARM_STATUS_STATE):
            return MAP_MYFOX_STATUS_STATE[
                self.executor.select_state(MYFOX_ALARM_STATUS_STATE)
            ]

        if self.executor.has_state(INTERNAL_CURRENT_ALARM_MODE_STATE):
            return MAP_INTERNAL_STATUS_STATE[
                self.executor.select_state(INTERNAL_CURRENT_ALARM_MODE_STATE)
            ]

        if self.executor.has_state(VERISURE_ALARM_PANEL_MAIN_ARM_TYPE_STATE):
            return MAP_VERISURE_STATUS_STATE[
                self.executor.select_state(VERISURE_ALARM_PANEL_MAIN_ARM_TYPE_STATE)
            ]

        return None

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        supported_features = 0

        if self.executor.has_command(COMMAND_ARM, COMMAND_ALARM_ON):
            supported_features |= SUPPORT_ALARM_ARM_AWAY

        if self.executor.has_command(COMMAND_ALARM_PARTIAL_1, COMMAND_ARM_PARTIAL_DAY):
            supported_features |= SUPPORT_ALARM_ARM_HOME

        if self.executor.has_command(
            COMMAND_PARTIAL, COMMAND_ALARM_PARTIAL_2, COMMAND_ARM_PARTIAL_NIGHT
        ):
            supported_features |= SUPPORT_ALARM_ARM_NIGHT

        if self.executor.has_command(COMMAND_SET_ALARM_STATUS):
            supported_features |= SUPPORT_ALARM_TRIGGER
            supported_features |= SUPPORT_ALARM_ARM_CUSTOM_BYPASS

        return supported_features

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.executor.async_execute_command(
            self.executor.select_command(COMMAND_DISARM, COMMAND_ALARM_OFF)
        )

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self.executor.async_execute_command(
            COMMAND_ALARM_PARTIAL_1, COMMAND_ARM_PARTIAL_DAY
        )

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        await self.executor.async_execute_command(
            self.executor.select_command(
                COMMAND_PARTIAL, COMMAND_ALARM_PARTIAL_2, COMMAND_ARM_PARTIAL_NIGHT
            )
        )

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self.executor.async_execute_command(
            self.executor.select_command(COMMAND_ARM, COMMAND_ALARM_ON)
        )

    async def async_alarm_trigger(self, code=None) -> None:
        """Send alarm trigger command."""
        await self.executor.async_execute_command(
            self.executor.select_command(COMMAND_SET_ALARM_STATUS, STATE_DETECTED)
        )

    async def async_alarm_arm_custom_bypass(self, code=None) -> None:
        """Send arm custom bypass command."""
        await self.executor.async_execute_command(
            self.executor.select_command(COMMAND_SET_ALARM_STATUS, STATE_UNDETECTED)
        )
