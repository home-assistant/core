"""Interfaces with iAlarm control panels."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import IAlarmDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a iAlarm alarm control panel based on a config entry."""
    coordinator: IAlarmDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities([IAlarmPanel(coordinator)], False)


class IAlarmPanel(
    CoordinatorEntity[IAlarmDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of an iAlarm device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = False

    def __init__(self, coordinator: IAlarmDataUpdateCoordinator) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)},
            manufacturer="Antifurto365 - Meian",
            name="iAlarm",
        )
        self._attr_unique_id = coordinator.mac

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self.coordinator.state

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self.coordinator.ialarm.disarm()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self.coordinator.ialarm.arm_stay()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self.coordinator.ialarm.arm_away()
