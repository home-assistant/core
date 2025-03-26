"""Support for Bosch Alarm Panel."""

from __future__ import annotations

from bosch_alarm_mode2 import Panel

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN


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


class AreaAlarmControlPanel(AlarmControlPanelEntity):
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
        self.panel = panel
        self._area = panel.areas[area_id]
        self._area_id = area_id
        self._attr_unique_id = f"{unique_id}_area_{area_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            via_device=(
                DOMAIN,
                unique_id,
            ),
        )

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
            return AlarmControlPanelState.ARMED_HOME
        if self._area.is_all_armed():
            return AlarmControlPanelState.ARMED_AWAY
        return None

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this panel."""
        await self.panel.area_disarm(self._area_id)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.panel.area_arm_part(self._area_id)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.panel.area_arm_all(self._area_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.panel.connection_status()

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        await super().async_added_to_hass()
        self._area.status_observer.attach(self.schedule_update_ha_state)
        self.panel.connection_status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        await super().async_will_remove_from_hass()
        self._area.status_observer.detach(self.schedule_update_ha_state)
        self.panel.connection_status_observer.detach(self.schedule_update_ha_state)
