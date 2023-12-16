"""Support for Comelit VEDO system."""
from __future__ import annotations

import logging

from aiocomelit.api import ComelitVedoAreaObject
from aiocomelit.const import ALARM_AREAS, AlarmAreaState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitVedoSystem

_LOGGER = logging.getLogger(__name__)

ALARM_ACTIONS: dict[str, str] = {
    "disable": "dis",  # Disarm
    "home": "p1",  # Arm P1
    "night": "p12",  # Arm P1+P2
    "away": "tot",  # Arm P1+P2 + IR / volumetric
}
ALARM_AREA_ARMED_STATUS: dict[str, int] = {
    "home_p1": 1,
    "home_p2": 2,
    "night": 3,
    "away": 4,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Comelit VEDO system alarm control panel devices."""

    coordinator: ComelitVedoSystem = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ComelitAlarmEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[ALARM_AREAS].values()
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

    def __init__(
        self,
        coordinator: ComelitVedoSystem,
        area: ComelitVedoAreaObject,
        config_entry_entry_id: str,
    ) -> None:
        """Initialize the alarm panel."""
        self._api = coordinator.api
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
        return self.coordinator.data[ALARM_AREAS][self._area_index]

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        if self._area.human_status in [AlarmAreaState.ANOMALY, AlarmAreaState.UNKNOWN]:
            return False
        return super().available

    @property
    def state(self) -> StateType:
        """Return the state of the alarm."""

        _LOGGER.debug(
            "Area %s status is: %s. Armed is %s",
            self._area.name,
            self._area.human_status,
            self._area.armed,
        )
        if self._area.human_status == AlarmAreaState.ARMED:
            if self._area.armed == ALARM_AREA_ARMED_STATUS["away"]:
                return STATE_ALARM_ARMED_AWAY
            if self._area.armed == ALARM_AREA_ARMED_STATUS["night"]:
                return STATE_ALARM_ARMED_NIGHT
            return STATE_ALARM_ARMED_HOME

        if self._area.human_status == AlarmAreaState.DISARMED:
            return STATE_ALARM_DISARMED
        if self._area.human_status == AlarmAreaState.ENTRY_DELAY:
            return STATE_ALARM_DISARMING
        if self._area.human_status == AlarmAreaState.EXIT_DELAY:
            return STATE_ALARM_ARMING
        if self._area.human_status == AlarmAreaState.TRIGGERED:
            return STATE_ALARM_TRIGGERED

        return None

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code != str(self._api.device_pin):
            return
        await self._api.set_zone_status(self._area.index, ALARM_ACTIONS["disable"])

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._api.set_zone_status(self._area.index, ALARM_ACTIONS["away"])

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._api.set_zone_status(self._area.index, ALARM_ACTIONS["home"])

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._api.set_zone_status(self._area.index, ALARM_ACTIONS["night"])
