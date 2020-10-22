"""Support for Canary alarm."""
from typing import Callable, List

from canary.api import LOCATION_MODE_AWAY, LOCATION_MODE_HOME, LOCATION_MODE_NIGHT

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import CanaryDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
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


class CanaryAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of a Canary alarm control panel."""

    def __init__(self, coordinator, location):
        """Initialize a Canary security camera."""
        super().__init__(coordinator)
        self._location_id = location.location_id
        self._location_name = location.name

    @property
    def location(self):
        """Return information about the location."""
        return self.coordinator.data["locations"][self._location_id]

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._location_name

    @property
    def unique_id(self):
        """Return the unique ID of the alarm."""
        return str(self._location_id)

    @property
    def state(self):
        """Return the state of the device."""
        if self.location.is_private:
            return STATE_ALARM_DISARMED

        mode = self.location.mode
        if mode.name == LOCATION_MODE_AWAY:
            return STATE_ALARM_ARMED_AWAY
        if mode.name == LOCATION_MODE_HOME:
            return STATE_ALARM_ARMED_HOME
        if mode.name == LOCATION_MODE_NIGHT:
            return STATE_ALARM_ARMED_NIGHT

        return None

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"private": self.location.is_private}

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.coordinator.canary.set_location_mode(
            self._location_id, self.location.mode.name, True
        )

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self.coordinator.canary.set_location_mode(self._location_id, LOCATION_MODE_HOME)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self.coordinator.canary.set_location_mode(self._location_id, LOCATION_MODE_AWAY)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self.coordinator.canary.set_location_mode(
            self._location_id, LOCATION_MODE_NIGHT
        )
