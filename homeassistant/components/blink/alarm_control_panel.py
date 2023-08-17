"""Support for Blink Alarm Control Panel."""
from __future__ import annotations

import asyncio
import logging

from blinkpy.blinkpy import Blink

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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
        sync_modules.append(BlinkSyncModuleHA(data, sync_name, sync_module))
    async_add_entities(sync_modules, update_before_add=True)


class BlinkSyncModuleHA(AlarmControlPanelEntity):
    """Representation of a Blink Alarm Control Panel."""

    _attr_icon = ICON
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_name = None
    _attr_has_entity_name = True

    def __init__(self, data, name: str, sync) -> None:
        """Initialize the alarm control panel."""
        self.data: Blink = data
        self.sync = sync
        self._name: str = name
        self._attr_unique_id: str = sync.serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sync.serial)},
            name=f"{DOMAIN} {name}",
            manufacturer=DEFAULT_BRAND,
        )

    async def async_update(self) -> None:
        """Update the state of the device."""
        if self.data.check_if_ok_to_update():
            _LOGGER.debug(
                "Initiating a blink.refresh() from BlinkSyncModule('%s') (%s)",
                self._name,
                self.data,
            )
            try:
                await self.data.refresh(force=True)
                self._attr_available = True
            except asyncio.TimeoutError:
                self._attr_available = False

            _LOGGER.info("Updating State of Blink Alarm Control Panel '%s'", self._name)

        self.sync.attributes["network_info"] = self.data.networks
        self.sync.attributes["associated_cameras"] = list(self.sync.cameras)
        self.sync.attributes[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        self._attr_extra_state_attributes = self.sync.attributes

    @property
    def state(self) -> StateType:
        """Return state of alarm."""
        return STATE_ALARM_ARMED_AWAY if self.sync.arm else STATE_ALARM_DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            await self.sync.async_arm(False)
            await self.sync.refresh()
            self.async_write_ha_state()
        except asyncio.TimeoutError:
            self._attr_available = False

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm command."""
        try:
            await self.sync.async_arm(True)
            await self.sync.refresh()
            self.async_write_ha_state()
        except asyncio.TimeoutError:
            self._attr_available = False
