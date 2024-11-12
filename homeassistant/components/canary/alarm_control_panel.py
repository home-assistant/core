"""Support for Canary alarm."""

from __future__ import annotations

from typing import Any

from canary.const import LOCATION_MODE_AWAY, LOCATION_MODE_HOME, LOCATION_MODE_NIGHT
from canary.model import Location

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CanaryDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canary alarm control panels based on a config entry."""
    coordinator: CanaryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    alarms = [
        CanaryAlarm(coordinator, location)
        for location_id, location in coordinator.data["locations"].items()
    ]

    async_add_entities(alarms, True)


class CanaryAlarm(
    CoordinatorEntity[CanaryDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of a Canary alarm control panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False

    def __init__(
        self, coordinator: CanaryDataUpdateCoordinator, location: Location
    ) -> None:
        """Initialize a Canary security camera."""
        super().__init__(coordinator)
        self._location_id: str = location.location_id
        self._attr_name = location.name
        self._attr_unique_id = str(self._location_id)

    @property
    def location(self) -> Location:
        """Return information about the location."""
        return self.coordinator.data["locations"][self._location_id]

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        if self.location.is_private:
            return AlarmControlPanelState.DISARMED

        mode = self.location.mode
        if mode.name == LOCATION_MODE_AWAY:
            return AlarmControlPanelState.ARMED_AWAY
        if mode.name == LOCATION_MODE_HOME:
            return AlarmControlPanelState.ARMED_HOME
        if mode.name == LOCATION_MODE_NIGHT:
            return AlarmControlPanelState.ARMED_NIGHT

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"private": self.location.is_private}

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self.coordinator.canary.set_location_mode(
            self._location_id, self.location.mode.name, True
        )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self.coordinator.canary.set_location_mode(self._location_id, LOCATION_MODE_HOME)

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self.coordinator.canary.set_location_mode(self._location_id, LOCATION_MODE_AWAY)

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self.coordinator.canary.set_location_mode(
            self._location_id, LOCATION_MODE_NIGHT
        )
