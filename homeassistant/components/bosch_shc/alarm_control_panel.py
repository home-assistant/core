"""Platform for alarm control panel integration."""
from __future__ import annotations

from boschshcpy import SHCIntrusionSystem, SHCSession

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DATA_SESSION, DOMAIN
from .entity import SHCDomainEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm control panel platform."""
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    alarm_control_panel = IntrusionSystemAlarmControlPanel(
        domain=session.intrusion_system,
        parent_id=session.information.unique_id,
        entry_id=config_entry.entry_id,
    )

    async_add_entities([alarm_control_panel])


class IntrusionSystemAlarmControlPanel(SHCDomainEntity, AlarmControlPanelEntity):
    """Representation of SHC intrusion detection control."""

    _attr_code_arm_required: bool = False
    _attr_should_poll: bool = False
    _attr_supported_features: int = (
        SUPPORT_ALARM_ARM_AWAY
        | SUPPORT_ALARM_ARM_HOME
        | SUPPORT_ALARM_ARM_CUSTOM_BYPASS
    )

    @property
    def state(self) -> StateType:
        """Return the state of the device."""
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_ARMING:
            return STATE_ALARM_ARMING
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_DISARMED:
            return STATE_ALARM_DISARMED
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_ARMED:
            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.FULL_PROTECTION
            ):
                return STATE_ALARM_ARMED_AWAY

            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.PARTIAL_PROTECTION
            ):
                return STATE_ALARM_ARMED_HOME

            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.CUSTOM_PROTECTION
            ):
                return STATE_ALARM_ARMED_CUSTOM_BYPASS
        return None

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._device.disarm()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._device.arm_full_protection()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._device.arm_partial_protection()

    def alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._device.arm_individual_protection()
