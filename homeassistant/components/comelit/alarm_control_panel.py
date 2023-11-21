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
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
        self._area = area
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{area.index}"
        self._attr_device_info = coordinator.platform_device_info(area)
        if area.p2:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_NIGHT

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
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

    @callback
    def _handle_arming_state_change(
        self,
        arming_state: AlarmAreaState,
        arming_mode: AlarmControlPanelEntityFeature | None,
    ) -> None:
        """Handle arming state update."""

        if arming_state == AlarmAreaState.UNKNOWN:
            self._attr_state = None
        elif arming_state == AlarmAreaState.DISARMED:
            self._attr_state = STATE_ALARM_DISARMED
        elif arming_state == AlarmAreaState.ENTRY_DELAY:
            self._attr_state = STATE_ALARM_DISARMING
        elif arming_state == AlarmAreaState.EXIT_DELAY:
            self._attr_state = STATE_ALARM_ARMING
        elif arming_state == AlarmAreaState.ARMED:
            self._attr_state = ARMING_MODE_TO_STATE.get(
                arming_mode, STATE_ALARM_ARMED_AWAY
            )
        else:
            _LOGGER.warning("Unhandled arming state: %s", arming_state)

        self.async_write_ha_state()
