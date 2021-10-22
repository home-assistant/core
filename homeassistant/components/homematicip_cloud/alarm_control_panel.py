"""Support for HomematicIP Cloud alarm control panel."""
from __future__ import annotations

import logging

from homematicip.functionalHomes import SecurityAndAlarmHome

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN as HMIPC_DOMAIN
from .hap import AsyncHome, HomematicipHAP

_LOGGER = logging.getLogger(__name__)

CONST_ALARM_CONTROL_PANEL_NAME = "HmIP Alarm Control Panel"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP alrm control panel from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    async_add_entities([HomematicipAlarmControlPanelEntity(hap)])


class HomematicipAlarmControlPanelEntity(AlarmControlPanelEntity):
    """Representation of the HomematicIP alarm control panel."""

    def __init__(self, hap: HomematicipHAP) -> None:
        """Initialize the alarm control panel."""
        self._home: AsyncHome = hap.home
        _LOGGER.info("Setting up %s", self.name)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return {
            "identifiers": {(HMIPC_DOMAIN, f"ACP {self._home.id}")},
            "name": self.name,
            "manufacturer": "eQ-3",
            "model": CONST_ALARM_CONTROL_PANEL_NAME,
            "via_device": (HMIPC_DOMAIN, self._home.id),
        }

    @property
    def state(self) -> str:
        """Return the state of the alarm control panel."""
        # check for triggered alarm
        if self._security_and_alarm.alarmActive:
            return STATE_ALARM_TRIGGERED

        activation_state = self._home.get_security_zones_activation()
        # check arm_away
        if activation_state == (True, True):
            return STATE_ALARM_ARMED_AWAY
        # check arm_home
        if activation_state == (False, True):
            return STATE_ALARM_ARMED_HOME

        return STATE_ALARM_DISARMED

    @property
    def _security_and_alarm(self) -> SecurityAndAlarmHome:
        return self._home.get_functionalHome(SecurityAndAlarmHome)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        await self._home.set_security_zones_activation(False, False)

    async def async_alarm_arm_home(self, code=None) -> None:
        """Send arm home command."""
        await self._home.set_security_zones_activation(False, True)

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        await self._home.set_security_zones_activation(True, True)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._home.on_update(self._async_device_changed)

    @callback
    def _async_device_changed(self, *args, **kwargs) -> None:
        """Handle entity state changes."""
        # Don't update disabled entities
        if self.enabled:
            _LOGGER.debug("Event %s (%s)", self.name, CONST_ALARM_CONTROL_PANEL_NAME)
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device Changed Event for %s (Alarm Control Panel) not fired. Entity is disabled",
                self.name,
            )

    @property
    def name(self) -> str:
        """Return the name of the generic entity."""
        name = CONST_ALARM_CONTROL_PANEL_NAME
        if self._home.name:
            name = f"{self._home.name} {name}"
        return name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Return if alarm control panel is available."""
        return self._home.connected

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.__class__.__name__}_{self._home.id}"
