"""Support for Freebox alarms."""

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FreeboxHomeCategory
from .entity import FreeboxHomeEntity
from .router import FreeboxConfigEntry, FreeboxRouter

FREEBOX_TO_STATUS = {
    "alarm1_arming": AlarmControlPanelState.ARMING,
    "alarm2_arming": AlarmControlPanelState.ARMING,
    "alarm1_armed": AlarmControlPanelState.ARMED_AWAY,
    "alarm2_armed": AlarmControlPanelState.ARMED_HOME,
    "alarm1_alert_timer": AlarmControlPanelState.TRIGGERED,
    "alarm2_alert_timer": AlarmControlPanelState.TRIGGERED,
    "alert": AlarmControlPanelState.TRIGGERED,
    "idle": AlarmControlPanelState.DISARMED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up alarm panel."""
    router = entry.runtime_data

    async_add_entities(
        (
            FreeboxAlarm(hass, router, node)
            for node in router.home_devices.values()
            if node["category"] == FreeboxHomeCategory.ALARM
        ),
        True,
    )


class FreeboxAlarm(FreeboxHomeEntity, AlarmControlPanelEntity):
    """Representation of a Freebox alarm."""

    _attr_code_arm_required = False

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize an alarm."""
        super().__init__(hass, router, node)

        # Commands
        self._command_trigger = self.get_command_id(
            node["type"]["endpoints"], "slot", "trigger"
        )
        self._command_arm_away = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm1"
        )
        self._command_arm_home = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm2"
        )
        self._command_disarm = self.get_command_id(
            node["type"]["endpoints"], "slot", "off"
        )
        self._command_state = self.get_command_id(
            node["type"]["endpoints"], "signal", "state"
        )

        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | (AlarmControlPanelEntityFeature.ARM_HOME if self._command_arm_home else 0)
            | AlarmControlPanelEntityFeature.TRIGGER
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.set_home_endpoint_value(self._command_disarm)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.set_home_endpoint_value(self._command_arm_away)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.set_home_endpoint_value(self._command_arm_home)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        await self.set_home_endpoint_value(self._command_trigger)

    async def async_update(self) -> None:
        """Update state."""
        state: str | None = await self.get_home_endpoint_value(self._command_state)
        if state:
            self._attr_alarm_state = FREEBOX_TO_STATUS.get(state)
        else:
            self._attr_alarm_state = None
