"""Support for Abode Security System alarm control panels."""
from __future__ import annotations

from jaraco.abode.devices.alarm import Alarm as AbodeAl

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbodeDevice, AbodeSystem
from .const import DOMAIN

ICON = "mdi:security"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Abode alarm control panel device."""
    data: AbodeSystem = hass.data[DOMAIN]
    async_add_entities(
        [AbodeAlarm(data, await hass.async_add_executor_job(data.abode.get_alarm))]
    )


class AbodeAlarm(AbodeDevice, alarm.AlarmControlPanelEntity):
    """An alarm_control_panel implementation for Abode."""

    _attr_icon = ICON
    _attr_name = None
    _attr_code_arm_required = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _device: AbodeAl

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self._device.is_standby:
            return STATE_ALARM_DISARMED
        if self._device.is_away:
            return STATE_ALARM_ARMED_AWAY
        if self._device.is_home:
            return STATE_ALARM_ARMED_HOME
        return None

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._device.set_standby()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._device.set_home()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._device.set_away()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            "device_id": self._device.device_id,
            "battery_backup": self._device.battery,
            "cellular_backup": self._device.is_cellular,
        }
