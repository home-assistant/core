"""Support for Ezviz alarm."""
from __future__ import annotations

import logging

from pyezviz.constants import DefenseModeType
from pyezviz.exceptions import HTTPError

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.components.ezviz.coordinator import EzvizDataUpdateCoordinator
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.helpers.entity import DeviceInfo
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Ezviz alarm control panel."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    async_add_entities([EzvizAlarm(coordinator)])


class EzvizAlarm(CoordinatorEntity, AlarmControlPanelEntity, RestoreEntity):
    """Representation of a Ezviz alarm control panel."""

    coordinator: EzvizDataUpdateCoordinator

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._location_id = "Home"
        self._state = STATE_ALARM_DISARMED
        self._name = "Ezviz Alarm"
        self._model = "Ezviz Alarm"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

    @property
    def location(self) -> str:
        """Return the location of the Alarm."""
        return self._location_id

    @property
    def name(self) -> str:
        """Return the name of the alarm."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the alarm."""
        return self._name

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._name)},
            "name": self._name,
            "model": self._model,
            "manufacturer": MANUFACTURER,
        }

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    def alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        try:
            service_switch = getattr(DefenseModeType, ATTR_HOME)
            self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)
            self._state = STATE_ALARM_DISARMED

        except HTTPError as err:
            raise HTTPError("Cannot disarm alarm") from err

    def alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        try:
            service_switch = getattr(DefenseModeType, ATTR_AWAY)
            self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)
            self._state = STATE_ALARM_ARMED_AWAY

        except HTTPError as err:
            raise HTTPError("Cannot arm alarm") from err

    def alarm_arm_night(self, code=None) -> None:
        """Send arm night command."""
        try:
            service_switch = getattr(DefenseModeType, ATTR_SLEEP)
            self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)
            self._state = STATE_ALARM_ARMED_NIGHT

        except HTTPError as err:
            raise HTTPError("Cannot arm alarm") from err
