"""Support for Ezviz alarm."""
from __future__ import annotations

from typing import Any

from pyezviz.constants import DefenseModeType
from pyezviz.exceptions import HTTPError

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AWAY,
    ATTR_HOME,
    ATTR_SLEEP,
    DATA_COORDINATOR,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import EzvizDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ezviz alarm control panel."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities([EzvizAlarm(coordinator)])


class EzvizAlarm(CoordinatorEntity, AlarmControlPanelEntity, RestoreEntity):
    """Representation of a Ezviz alarm control panel."""

    coordinator: EzvizDataUpdateCoordinator
    _attr_name = "Ezviz Alarm"
    _attr_supported_features = SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT
    _attr_code_arm_required = False

    def __init__(self, coordinator: EzvizDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_state = STATE_ALARM_DISARMED
        self._model = "Ezviz Alarm"
        self._attr_unique_id = "Ezviz Alarm"
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._attr_name)},
            "name": self._attr_name,
            "model": self._model,
            "manufacturer": MANUFACTURER,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        if (
            state.state == STATE_ALARM_DISARMED
            or STATE_ALARM_ARMED_AWAY
            or STATE_ALARM_ARMED_NIGHT
        ):
            self._attr_state = state.state

    def alarm_disarm(self, code: Any = None) -> None:
        """Send disarm command."""
        try:
            service_switch = getattr(DefenseModeType, ATTR_HOME)
            self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)

        except HTTPError as err:
            raise HTTPError("Cannot disarm alarm") from err

        self._attr_state = STATE_ALARM_DISARMED

    def alarm_arm_away(self, code: Any = None) -> None:
        """Send arm away command."""
        try:
            service_switch = getattr(DefenseModeType, ATTR_AWAY)
            self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)

        except HTTPError as err:
            raise HTTPError("Cannot arm alarm") from err

        self._attr_state = STATE_ALARM_ARMED_AWAY

    def alarm_arm_night(self, code: Any = None) -> None:
        """Send arm night command."""
        try:
            service_switch = getattr(DefenseModeType, ATTR_SLEEP)
            self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)

        except HTTPError as err:
            raise HTTPError("Cannot arm alarm") from err

        self._attr_state = STATE_ALARM_ARMED_NIGHT
