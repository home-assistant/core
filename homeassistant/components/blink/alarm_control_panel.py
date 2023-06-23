"""Support for Blink Alarm Control Panel."""
from __future__ import annotations

import asyncio
import contextlib
import logging

from blinkpy.blinkpy import Blink, BlinkSyncModule

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_ATTRIBUTION, DEFAULT_BRAND, DOMAIN
from .coordinator import BlinkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:security"


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Blink Alarm Control Panels."""
    coordinator: BlinkUpdateCoordinator = hass.data[DOMAIN][config.entry_id]

    sync_modules = []
    for sync_name, sync_module in coordinator.api.sync.items():
        sync_modules.append(BlinkSyncModuleHA(coordinator, sync_name, sync_module))
    async_add_entities(sync_modules)


class BlinkSyncModuleHA(
    CoordinatorEntity[BlinkUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of a Blink Alarm Control Panel."""

    _attr_icon = ICON
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_name = None
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BlinkUpdateCoordinator, name: str, sync: BlinkSyncModule
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self.api: Blink = coordinator.api
        self.sync = sync
        self._name: str = name
        self._attr_unique_id: str = sync.serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sync.serial)},
            name=f"{DOMAIN} {name}",
            manufacturer=DEFAULT_BRAND,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self.sync.attributes["network_info"] = self.api.networks
        self.sync.attributes["associated_cameras"] = list(self.sync.cameras)
        self.sync.attributes[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        self._attr_extra_state_attributes = self.sync.attributes
        self._attr_state = (
            STATE_ALARM_ARMED_AWAY if self.sync.arm else STATE_ALARM_DISARMED
        )

        self.async_write_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            await self.sync.async_arm(False)
            await self.coordinator.async_refresh()
        except asyncio.TimeoutError:
            self._attr_available = False

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm command."""
        try:
            await self.sync.async_arm(True)
            await self.coordinator.async_refresh()
        except asyncio.TimeoutError:
            self._attr_available = False
