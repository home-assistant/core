"""Support for Blink Alarm Control Panel."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import SUPPORT_ALARM_ARM_AWAY
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
)

from .const import DEFAULT_ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:security"


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the Blink Alarm Control Panels."""
    data = hass.data[DOMAIN][config.entry_id]

    sync_modules = []
    for sync_name, sync_module in data.sync.items():
        sync_modules.append(BlinkSyncModule(data, sync_name, sync_module))
    async_add_entities(sync_modules)


class BlinkSyncModule(AlarmControlPanelEntity):
    """Representation of a Blink Alarm Control Panel."""

    _attr_icon = ICON
    _attr_supported_features = SUPPORT_ALARM_ARM_AWAY

    def __init__(self, data, name, sync):
        """Initialize the alarm control panel."""
        self.data = data
        self.sync = sync
        self._name = name
        self._attr_unique_id = sync.serial
        self._attr_name = f"{DOMAIN} {name}"

    def update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating Blink Alarm Control Panel %s", self._name)
        self.data.refresh()
        self._attr_state = (
            STATE_ALARM_ARMED_AWAY if self.sync.arm else STATE_ALARM_DISARMED
        )
        self.sync.attributes["network_info"] = self.data.networks
        self.sync.attributes["associated_cameras"] = list(self.sync.cameras)
        self.sync.attributes[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        self._attr_extra_state_attributes = self.sync.attributes

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.sync.arm = False
        self.sync.refresh()

    def alarm_arm_away(self, code=None):
        """Send arm command."""
        self.sync.arm = True
        self.sync.refresh()
