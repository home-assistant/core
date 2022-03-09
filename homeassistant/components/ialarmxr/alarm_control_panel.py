"""Interfaces with iAlarmXR control panels."""

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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


class IAlarmXRPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of an iAlarmXR device."""

    def __init__(self, coordinator: IAlarmXRDataUpdateCoordinator) -> None:
        """Initialize the alarm panel."""
        super().__init__(coordinator)
        self.coordinator: IAlarmXRDataUpdateCoordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Antifurto365 - Meian",
            name=self.name,
        )

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return self.coordinator.mac

    @property
    def name(self) -> str:
        """Return the name."""
        return "iAlarmXR"

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self.coordinator.state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        self.coordinator.ialarmxr.disarm()

    def alarm_arm_home(self, code=None) -> None:
        """Send arm home command."""
        self.coordinator.ialarmxr.arm_stay()

    def alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        self.coordinator.ialarmxr.arm_away()
