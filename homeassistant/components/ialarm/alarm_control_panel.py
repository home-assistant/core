"""Interfaces with iAlarm control panels."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up a iAlarm alarm control panel based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([IAlarmPanel(coordinator)], False)


class IAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of an iAlarm device."""

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Antifurto365 - Meian",
        }

    @property
    def unique_id(self):
        """Return a unique id."""
        return self.coordinator.mac

    @property
    def name(self):
        """Return the name."""
        return "iAlarm"

    @property
    def state(self):
        """Return the state of the device."""
        return self.coordinator.state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.coordinator.ialarm.disarm()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self.coordinator.ialarm.arm_stay()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self.coordinator.ialarm.arm_away()
