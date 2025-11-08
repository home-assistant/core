"""Support for Bosch Alarm Panel."""

from __future__ import annotations

from bosch_alarm_mode2 import Panel

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BoschAlarmAreaEntity
from .types import BoschAlarmConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up control panels for each area."""
    panel = config_entry.runtime_data

    async_add_entities(
        AreaAlarmControlPanel(
            panel,
            area_id,
            config_entry.unique_id or config_entry.entry_id,
        )
        for area_id in panel.areas
    )


PARALLEL_UPDATES = 0

BG_PANELS = {
    "D7412GV4",
    "D9412GV4",
    "B3512 (US1B)",
    "B4512 (US1B)",
    "B5512 (US1B)",
    "B6512 (US1B)",
    "B8512G (US1A)",
    "B9512G (US1A)",
}


class AreaAlarmControlPanel(BoschAlarmAreaEntity, AlarmControlPanelEntity):
    """An alarm control panel entity for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    _attr_code_arm_required = False
    _attr_name = None

    def __init__(self, panel: Panel, area_id: int, unique_id: str) -> None:
        """Initialise a Bosch Alarm control panel entity."""
        super().__init__(panel, area_id, unique_id, True, False, True)
        self._attr_unique_id = self._area_unique_id

        # Enable ARM_NIGHT for B/G Panels
        if self.panel.model in BG_PANELS:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_NIGHT

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        if self._area.is_triggered():
            return AlarmControlPanelState.TRIGGERED
        if self._area.is_disarmed():
            return AlarmControlPanelState.DISARMED
        if self._area.is_arming():
            return AlarmControlPanelState.ARMING
        if self._area.is_pending():
            return AlarmControlPanelState.PENDING
        if self._area.is_part_armed():
            # For B/G Panels, distinguish between Arm Home (Part On Delay)
            # and Arm Night (Part On Instant)
            if self._area.status == 0x02:  # Part On Instant
                return AlarmControlPanelState.ARMED_NIGHT
            return AlarmControlPanelState.ARMED_HOME
        if self._area.is_all_armed():
            return AlarmControlPanelState.ARMED_AWAY

        return None

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this panel."""
        await self.panel.area_disarm(self._area_id)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.panel.area_arm_part(self._area_id, delay=True)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command for B/G Panels."""
        await self.panel.area_arm_part(self._area_id, delay=False)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.panel.area_arm_all(self._area_id)
