"""button platform for Netis Router.

Provides a "Reboot" button entity. When pressed, it calls ``system.reboot``
via ubus, which restarts the router. Expect approximately 60 seconds of
downtime; the coordinator will mark all entities as ``unavailable`` and
recover automatically once the router comes back online.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetisCoordinator
from .entity import NetisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netis buttons."""
    coordinator: NetisCoordinator = entry.runtime_data
    async_add_entities([NetisRebootButton(coordinator)])


class NetisRebootButton(NetisEntity, ButtonEntity):
    """Reboot the router."""

    _attr_name = "Reboot"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: NetisCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-reboot"

    async def async_press(self) -> None:
        """Send the reboot command."""
        _LOGGER.info("Rebooting Netis router %s", self.coordinator.config_entry.title)
        await self.coordinator.client.reboot()
        # Expect a short outage; let the coordinator recover naturally.
