"""Support for Bosch Alarm Panel."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschAlarmConfigEntry, BoschAlarmCoordinator


async def async_setup_entry(
    hass: HomeAssistant | None,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up control panels for each area."""
    coordinator: BoschAlarmCoordinator = config_entry.runtime_data

    async_add_entities(
        AreaAlarmControlPanel(
            coordinator,
            area_id,
        )
        for area_id in coordinator.panel.areas
    )


class AreaAlarmControlPanel(
    CoordinatorEntity[BoschAlarmCoordinator], AlarmControlPanelEntity
):
    """An alarm control panel entity for a bosch alarm panel."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschAlarmCoordinator,
        area_id: int,
    ) -> None:
        """Initialise a Bosch Alarm control panel entity."""
        super().__init__(coordinator, area_id)
        self._area = coordinator.panel.areas[area_id]
        self._area_id = area_id
        self._attr_name = self._area.name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_area_{area_id}"
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=f"Bosch {coordinator.panel.model}",
            manufacturer="Bosch Security Systems",
            model=coordinator.panel.model,
            sw_version=coordinator.panel.firmware_version,
        )
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
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
        await self.coordinator.panel.area_disarm(self._area_id)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.coordinator.panel.area_arm_part(self._area_id)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.coordinator.panel.area_arm_all(self._area_id)

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        await super().async_added_to_hass()
        self._area.status_observer.attach(self.schedule_update_ha_state)
        self._area.alarm_observer.attach(self.schedule_update_ha_state)
        self._area.ready_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        self._area.status_observer.detach(self.schedule_update_ha_state)
        self._area.alarm_observer.detach(self.schedule_update_ha_state)
        self._area.ready_observer.detach(self.schedule_update_ha_state)
