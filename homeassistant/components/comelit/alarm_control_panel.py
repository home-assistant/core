"""Support for Comelit VEDO system."""

from __future__ import annotations

import logging
from typing import cast

from aiocomelit.api import ComelitVedoAreaObject
from aiocomelit.const import AlarmAreaState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ComelitConfigEntry, ComelitVedoSystem

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

AWAY = "away"
DISABLE = "disable"
HOME = "home"
HOME_P1 = "home_p1"
HOME_P2 = "home_p2"
NIGHT = "night"

ALARM_ACTIONS: dict[str, str] = {
    DISABLE: "dis",  # Disarm
    HOME: "p1",  # Arm P1
    NIGHT: "p12",  # Arm P1+P2
    AWAY: "tot",  # Arm P1+P2 + IR / volumetric
}


ALARM_AREA_ARMED_STATUS: dict[str, int] = {
    DISABLE: 0,
    HOME_P1: 1,
    HOME_P2: 2,
    NIGHT: 3,
    AWAY: 4,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Comelit VEDO system alarm control panel devices."""

    coordinator = cast(ComelitVedoSystem, config_entry.runtime_data)

    async_add_entities(
        ComelitAlarmEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data["alarm_areas"].values()
    )


class ComelitAlarmEntity(CoordinatorEntity[ComelitVedoSystem], AlarmControlPanelEntity):
    """Representation of a Ness alarm panel."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ComelitVedoSystem,
        area: ComelitVedoAreaObject,
        config_entry_entry_id: str,
    ) -> None:
        """Initialize the alarm panel."""
        self._area_index = area.index
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{area.index}"
        self._attr_device_info = coordinator.platform_device_info(area, "area")
        if area.p2:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_NIGHT

    @property
    def _area(self) -> ComelitVedoAreaObject:
        """Return area object."""
        return self.coordinator.data["alarm_areas"][self._area_index]

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        if self._area.human_status in [AlarmAreaState.ANOMALY, AlarmAreaState.UNKNOWN]:
            return False
        return super().available

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""

        _LOGGER.debug(
            "Area %s status is: %s. Armed is %s",
            self._area.name,
            self._area.human_status,
            self._area.armed,
        )
        if self._area.human_status == AlarmAreaState.ARMED:
            if self._area.armed == ALARM_AREA_ARMED_STATUS[AWAY]:
                return AlarmControlPanelState.ARMED_AWAY
            if self._area.armed == ALARM_AREA_ARMED_STATUS[NIGHT]:
                return AlarmControlPanelState.ARMED_NIGHT
            return AlarmControlPanelState.ARMED_HOME

        return {
            AlarmAreaState.DISARMED: AlarmControlPanelState.DISARMED,
            AlarmAreaState.ENTRY_DELAY: AlarmControlPanelState.DISARMING,
            AlarmAreaState.EXIT_DELAY: AlarmControlPanelState.ARMING,
            AlarmAreaState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
        }.get(self._area.human_status)

    async def _async_update_state(self, area_state: AlarmAreaState, armed: int) -> None:
        """Update state after action."""
        self._area.human_status = area_state
        self._area.armed = armed
        await self.async_update_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code != str(self.coordinator.api.device_pin):
            return
        await self.coordinator.api.set_zone_status(
            self._area.index, ALARM_ACTIONS[DISABLE]
        )
        await self._async_update_state(
            AlarmAreaState.DISARMED, ALARM_AREA_ARMED_STATUS[DISABLE]
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.coordinator.api.set_zone_status(
            self._area.index, ALARM_ACTIONS[AWAY]
        )
        await self._async_update_state(
            AlarmAreaState.ARMED, ALARM_AREA_ARMED_STATUS[AWAY]
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.coordinator.api.set_zone_status(
            self._area.index, ALARM_ACTIONS[HOME]
        )
        await self._async_update_state(
            AlarmAreaState.ARMED, ALARM_AREA_ARMED_STATUS[HOME_P1]
        )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self.coordinator.api.set_zone_status(
            self._area.index, ALARM_ACTIONS[NIGHT]
        )
        await self._async_update_state(
            AlarmAreaState.ARMED, ALARM_AREA_ARMED_STATUS[NIGHT]
        )
