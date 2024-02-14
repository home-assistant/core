"""Support for Blink Alarm Control Panel."""
from __future__ import annotations

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
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
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: BlinkUpdateCoordinator, name: str, sync: BlinkSyncModule
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self.api: Blink = coordinator.api
        self.sync = sync
        self._attr_unique_id: str = sync.serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sync.serial)},
            name=f"{DOMAIN} {name}",
            manufacturer=DEFAULT_BRAND,
            serial_number=sync.serial,
            sw_version=sync.version,
        )
        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self._update_attr()
        super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Update attributes for alarm control panel."""
        self.sync.attributes["network_info"] = self.api.networks
        self.sync.attributes["associated_cameras"] = list(self.sync.cameras)
        self.sync.attributes[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        self._attr_extra_state_attributes = self.sync.attributes
        self._attr_state = (
            STATE_ALARM_ARMED_AWAY if self.sync.arm else STATE_ALARM_DISARMED
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            await self.sync.async_arm(False)

        except TimeoutError as er:
            raise HomeAssistantError("Blink failed to disarm camera") from er

        await self.coordinator.async_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm command."""
        try:
            await self.sync.async_arm(True)

        except TimeoutError as er:
            raise HomeAssistantError("Blink failed to arm camera away") from er

        await self.coordinator.async_refresh()
