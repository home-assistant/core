"""Interfaces with EPS control panels."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EPSDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a EPS alarm control panel based on a config entry."""
    coordinator: EPSDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EPSPanel(coordinator)], False)


class EPSPanel(CoordinatorEntity[EPSDataUpdateCoordinator], AlarmControlPanelEntity):
    """Representation of an EPS device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(self, coordinator: EPSDataUpdateCoordinator) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.site)},
            manufacturer="EPS Homiris",
            name="EPS",
        )
        self._attr_unique_id = coordinator.site

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self.coordinator.state

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        # The update takes roughly 5s to be applied, so we manually update it here.
        # In case it fails server side, it will be anyway updated at next scan
        if self.coordinator.eps_api.disarm(silent=True):
            self.coordinator.state = STATE_ALARM_DISARMED
            self.schedule_update_ha_state()

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        # The update takes roughly 5s to be applied, so we manually update it here.
        # In case it fails server side, it will be anyway updated at next scan
        if self.coordinator.eps_api.arm_night(silent=True):
            self.coordinator.state = STATE_ALARM_ARMED_NIGHT
            self.schedule_update_ha_state()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        # The update takes roughly 5s to be applied, so we manually update it here.
        # In case it fails server side, it will be anyway updated at next scan
        if self.coordinator.eps_api.arm_away(silent=False):
            self.coordinator.state = STATE_ALARM_ARMED_AWAY
            self.schedule_update_ha_state()
