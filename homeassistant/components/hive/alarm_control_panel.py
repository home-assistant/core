"""Support for the Hive alarm."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HiveEntity

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
HIVETOHA = {
    "home": AlarmControlPanelState.DISARMED,
    "asleep": AlarmControlPanelState.ARMED_NIGHT,
    "away": AlarmControlPanelState.ARMED_AWAY,
    "sos": AlarmControlPanelState.TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    if devices := hive.session.deviceList.get("alarm_control_panel"):
        async_add_entities(
            [HiveAlarmControlPanelEntity(hive, dev) for dev in devices], True
        )


class HiveAlarmControlPanelEntity(HiveEntity, AlarmControlPanelEntity):
    """Representation of a Hive alarm."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )
    _attr_code_arm_required = False

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.hive.alarm.setMode(self.device, "home")

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self.hive.alarm.setMode(self.device, "asleep")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.hive.alarm.setMode(self.device, "away")

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        await self.hive.alarm.setMode(self.device, "sos")

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.alarm.getAlarm(self.device)
        self._attr_available = self.device["deviceData"].get("online")
        if self._attr_available:
            if self.device["status"]["state"]:
                self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
            else:
                self._attr_alarm_state = HIVETOHA[self.device["status"]["mode"]]
