"""Interfaces with iAlarmXR control panels."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IAlarmXRDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a iAlarmXR alarm control panel based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IAlarmXRPanel(coordinator)])


class IAlarmXRPanel(
    CoordinatorEntity[IAlarmXRDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of an iAlarmXR device."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_name = "iAlarm_XR"
    _attr_icon = "mdi:security"

    def __init__(self, coordinator: IAlarmXRDataUpdateCoordinator) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.mac
        self._attr_device_info = DeviceInfo(
            manufacturer="Antifurto365 - Meian",
            name=self.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, coordinator.mac)},
        )

    @property
    def state(self) -> str | None:
        """Return the state of the device."""

        state = STATE_UNKNOWN

        if self.coordinator.state == "disarmed":
            state = STATE_ALARM_DISARMED
        elif self.coordinator.state == "armed_away":
            state = STATE_ALARM_ARMED_AWAY
        elif self.coordinator.state == "armed_home":
            state = STATE_ALARM_ARMED_HOME
        elif self.coordinator.state == "triggered":
            state = STATE_ALARM_TRIGGERED

        return state

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self.coordinator.ialarmxr.disarm()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self.coordinator.ialarmxr.arm_stay()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self.coordinator.ialarmxr.arm_away()
