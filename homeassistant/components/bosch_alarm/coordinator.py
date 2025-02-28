"""Coordinator for Bosch Alarm Panel."""

from __future__ import annotations

import logging

from bosch_alarm_mode2 import Panel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BoschAlarmCoordinator(DataUpdateCoordinator):
    """Bosch alarm coordinator."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, panel: Panel
    ) -> None:
        """Initialize bosch alarm coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Bosch {config_entry.data[CONF_MODEL]}",
            config_entry=config_entry,
        )
        self.panel: Panel = panel

        # The config flow sets the entries unique id to the serial number if available
        # If the panel doesn't expose it's serial number, use the entry id as a unique id instead.
        self.unique_id = config_entry.unique_id or config_entry.entry_id
        self.model = config_entry.data[CONF_MODEL]
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=f"Bosch {self.model}",
            manufacturer="Bosch Security Systems",
            model=self.model,
            sw_version=self.panel.firmware_version,
        )

        panel.connection_status_observer.attach(self._on_connection_status_change)

    def _on_connection_status_change(self):
        self.last_update_success = self.panel.connection_status()

    async def area_disarm(self, area_id) -> None:
        """Disarm an area."""
        await self.panel.area_disarm(area_id)

    async def area_arm_part(self, area_id) -> None:
        """Send arm home command."""
        await self.panel.area_arm_part(area_id)

    async def area_arm_all(self, area_id) -> None:
        """Send arm away command."""
        await self.panel.area_arm_all(area_id)

    async def async_shutdown(self) -> None:
        """Run shutdown clean up."""
        await super().async_shutdown()
        self.panel.connection_status_observer.detach(self._on_connection_status_change)
        await self.panel.disconnect()
