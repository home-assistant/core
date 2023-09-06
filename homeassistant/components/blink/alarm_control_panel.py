"""Support for Blink Alarm Control Panel."""
from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_ATTRIBUTION, DEFAULT_BRAND, DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:security"


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Blink Alarm Control Panels."""
    data = hass.data[DOMAIN][config.entry_id]

    sync_modules = []
    for sync_name, sync_module in data.sync.items():
        sync_modules.append(BlinkSyncModule(data, sync_name, sync_module))
    async_add_entities(sync_modules)


class BlinkSyncModule(AlarmControlPanelEntity):
    """Representation of a Blink Alarm Control Panel."""

    _attr_icon = ICON
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_name = None
    _attr_has_entity_name = True

    def __init__(self, data, name, sync):
        """Initialize the alarm control panel."""
        self.data = data
        self.sync = sync
        self._name = name
        self._attr_unique_id = sync.serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sync.serial)},
            name=f"{DOMAIN} {name}",
            manufacturer=DEFAULT_BRAND,
        )

    def update(self) -> None:
        """Update the state of the device."""
        if self.data.check_if_ok_to_update():
            _LOGGER.debug(
                "Initiating a blink.refresh() from BlinkSyncModule('%s') (%s)",
                self._name,
                self.data,
            )
            self.data.refresh()
            _LOGGER.info("Updating State of Blink Alarm Control Panel '%s'", self._name)

        self._attr_state = (
            STATE_ALARM_ARMED_AWAY if self.sync.arm else STATE_ALARM_DISARMED
        )
        self.sync.attributes["network_info"] = self.data.networks
        self.sync.attributes["associated_cameras"] = list(self.sync.cameras)
        self.sync.attributes[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        self._attr_extra_state_attributes = self.sync.attributes

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self.sync.arm = False
        self.sync.refresh()

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm command."""
        self.sync.arm = True
        self.sync.refresh()
